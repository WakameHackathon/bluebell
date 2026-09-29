"""Runtime for the vendored aftercare skills under ``skills/<skill-id>/``.

Each skill is an *agent skill*: a ``SKILL.md`` of operating rules plus
``references/*.schema.json`` excerpts of the central contract. A skill is not a
function you call, so "invoking" one means the host does all of this:

1. build a real contract request envelope from stored artifacts
   (``build_request``) and validate it against ``$defs.<skill>Request``;
2. hand the skill's own ``SKILL.md`` rules to the model together with that
   request, and require a JSON result envelope back (``render_task``);
3. validate the model's envelope *and* the artifact inside ``data`` against
   ``$defs.<skill>Result`` (``validate_result``);
4. register a completed artifact so downstream skills can reference it.

Steps 1, 3 and 4 are enforced here. The module deliberately does not invent
business facts: anything the skills require from the host (platform views,
ledgers, confirmations, executions) must already exist as a registered
artifact, otherwise the call is refused with a ``missing_input`` issue, which
is the contract-correct outcome rather than a fabricated success.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skill_schema import SchemaError, format_errors, is_valid, validate

CONTRACT_VERSION = "1.0.0"

# Artifact kinds the host itself is responsible for; no vendored skill produces
# them. A call that needs one is refused until the host registers it.
HOST_PROVIDED_KINDS = {
    "PlatformView",
    "OperationLedger",
    "ExecutionReceipt",
    "UserDecision",
    "UserTurn",
    "FailureEvent",
    "TaskSnapshot",
}

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_REF_FIELDS = {"artifact_id", "kind", "revision"}

# Constructs that appear inside the request envelope rather than as artifacts
# produced by a skill. A reference to one is legal only for the input that
# declares it (``goal_step`` -> Step, ``user_turn`` -> UserTurn).
ENVELOPE_KINDS = {"Step", "Fact", "Money", "UserTurn"}


def deref(defs: dict, node: Any) -> dict:
    """Follow ``$ref`` links until a concrete schema node is reached."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 16:
        pointer = str(node["$ref"])
        if not pointer.startswith("#/$defs/"):
            break
        node = defs.get(pointer.rsplit("/", 1)[-1], node)
        seen += 1
    return node if isinstance(node, dict) else {}


def is_artifact_ref(node: Any) -> bool:
    """True for the ``{artifact_id, kind, revision}`` reference shape."""
    if not isinstance(node, dict) or node.get("type") != "object":
        return False
    return set(node.get("properties") or {}) == _REF_FIELDS


def artifact_kind(node: Any) -> str | None:
    """The kind a reference must carry.

    Usually a ``const``; ``source_artifacts`` instead enumerates several
    allowed kinds, which means "any registered artifact" rather than one type.
    """
    if not is_artifact_ref(node):
        return None
    kind = node["properties"]["kind"] or {}
    if "const" in kind:
        return kind["const"]
    choices = kind.get("enum")
    if isinstance(choices, list) and len(choices) == 1:
        return choices[0]
    return None


def classify(defs: dict, node: Any) -> tuple[str, str | None, bool, str | None]:
    """Return ``(shape, kind, nullable, item_type)`` for one request input.

    ``shape`` is ``"ref"``, ``"array"``, ``"object"`` or ``"plain"``. For an
    array, ``kind`` is set only when its items are artifact references; a plain
    ``array`` of strings (``approved_file_refs``) keeps ``item_type`` instead.
    """
    node = deref(defs, node)
    if "anyOf" in node:
        branches = [deref(defs, b) for b in node["anyOf"]]
        nullable = any(b.get("type") == "null" for b in branches)
        branch = next((b for b in branches if b.get("type") != "null"), {})
        shape, kind, _, item_type = classify(defs, branch)
        return shape, kind, nullable, item_type
    if is_artifact_ref(node):
        return "ref", artifact_kind(node), False, None
    if node.get("type") == "array":
        items = deref(defs, node.get("items") or {})
        if is_artifact_ref(items):
            return "array", artifact_kind(items), False, None
        return "array", None, False, items.get("type")
    if node.get("type") == "object":
        return "object", None, False, None
    return "plain", node.get("type"), False, None


class SkillNotFound(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the tiny YAML frontmatter block at the top of a SKILL.md.

    Only flat ``key: value`` pairs and the ``metadata:`` nesting used by these
    skills are supported, so PyYAML is not needed.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    nested: str | None = None
    for raw in match.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key, _, value = raw.strip().partition(":")
        value = value.strip()
        if indent and nested:
            meta.setdefault(nested, {})[key] = value
        elif value:
            meta[key] = value
            nested = None
        else:
            nested = key
            meta[key] = {}
    return meta, text[match.end():]


class SkillPackage:
    """One vendored skill directory."""

    def __init__(self, skill_id: str, path: Path, entry: dict[str, Any]):
        self.skill_id = skill_id
        self.path = path
        self.entry = entry
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            raise SkillNotFound(f"{skill_id}: missing {skill_md}")
        text = skill_md.read_text(encoding="utf-8")
        self.frontmatter, self.instructions = _parse_frontmatter(text)
        meta = self.frontmatter.get("metadata") or {}
        # Prefer the catalog; fall back to the skill's own frontmatter.
        self.version = str(
            entry.get("skill_version") or meta.get("version") or "1.0.0"
        )
        self.description = str(self.frontmatter.get("description", "")).strip()

    @property
    def request_def(self) -> str:
        return self.entry["input_schema"]

    @property
    def result_def(self) -> str:
        return self.entry["result_schema"]

    @property
    def output_kind(self) -> str:
        return self.entry["output_kind"]

    def required_inputs(self) -> list[str]:
        return list((self.entry.get("required_inputs") or {}).keys())

    def schema(self) -> dict[str, Any]:
        """The skill's own contract excerpt (``references/*.schema.json``)."""
        rel = self.entry.get("schema")
        if not rel:
            return {}
        path = self.path / rel
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def reference_docs(self) -> list[Path]:
        refs = self.path / "references"
        if not refs.is_dir():
            return []
        return sorted(p for p in refs.glob("*.md"))

    def summary(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "display_name": self.entry.get("display_name"),
            "skill_version": self.version,
            "layer": self.entry.get("layer", "common"),
            "output_kind": self.output_kind,
            "implemented": bool(self.entry.get("implemented", True)),
            "description": self.description,
            "required_inputs": sorted(self.required_inputs()),
            "typical_next_skills": self.entry.get("typical_next_skills", []),
        }


class SkillRegistry:
    """Loads ``skills/*/SKILL.md`` for every catalog entry that has a package."""

    def __init__(self, root: Path, catalog: dict[str, Any], contracts: dict[str, Any]):
        self.root = Path(root)
        self.catalog = catalog
        self.contracts = contracts
        self.defs: dict[str, Any] = contracts.get("$defs", {})
        self.skills: dict[str, SkillPackage] = {}
        self.missing: dict[str, str] = {}
        for entry in catalog.get("skills", []):
            skill_id = entry["skill_id"]
            rel = entry.get("package")
            if not entry.get("implemented") or not rel:
                self.missing[skill_id] = "catalog 未提供 package（未实现）"
                continue
            path = self.root / rel
            if not (path / "SKILL.md").is_file():
                self.missing[skill_id] = f"缺少 {rel}/SKILL.md"
                continue
            for key in ("input_schema", "result_schema"):
                if entry.get(key) not in self.defs:
                    self.missing[skill_id] = f"中央契约缺少 $defs.{entry.get(key)}"
                    break
            else:
                self.skills[skill_id] = SkillPackage(skill_id, path, entry)

    # -- lookup -----------------------------------------------------------
    def get(self, skill_id: str) -> SkillPackage:
        skill = self.skills.get(skill_id)
        if skill is None:
            reason = self.missing.get(skill_id, "不在 catalog 中")
            raise SkillNotFound(f"{skill_id}: {reason}")
        return skill

    def status(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "catalog_version": self.catalog.get("version"),
            "loaded": [self.skills[k].summary() for k in sorted(self.skills)],
            "unavailable": dict(sorted(self.missing.items())),
        }

    # -- step 1: build and validate a request ------------------------------
    def build_request(
        self,
        skill: SkillPackage,
        task_id: str,
        task_snapshot_ref: dict[str, Any],
        task_revision: int,
        inputs: dict[str, Any],
        mode: str = "self",
    ) -> dict[str, Any]:
        """Assemble the wire envelope and check it against the contract.

        ``task_snapshot`` is a *reference* to a registered TaskSnapshot, not a
        literal, so the caller must register one first.
        """
        body = {
            "contract_version": CONTRACT_VERSION,
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
            "call_id": _new_id("call"),
            "task_id": task_id,
            "expected_task_revision": task_revision,
            "mode": mode,
            "task_snapshot": task_snapshot_ref,
            "inputs": inputs,
        }
        errors = format_errors(self.defs[skill.request_def], body, self.contracts)
        if errors:
            raise SchemaError(errors, skill.request_def)
        return body

    def missing_inputs(self, skill: SkillPackage, inputs: dict[str, Any]) -> list[str]:
        """Required inputs that are absent, as contract field names."""
        return [name for name in skill.required_inputs() if inputs.get(name) is None]

    # -- step 3: validate the model's answer -------------------------------
    def validate_result(self, skill: SkillPackage, candidate: Any) -> tuple[dict | None, list[str]]:
        """Return ``(result, [])`` when valid, else ``(None, errors)``."""
        if not isinstance(candidate, dict):
            return None, [f"$: 期望一个 JSON 对象，收到 {type(candidate).__name__}"]
        errors = format_errors(self.defs[skill.result_def], candidate, self.contracts)
        if errors:
            return None, errors
        if candidate["skill_id"] != skill.skill_id:
            return None, [f"$.skill_id: 应为 {skill.skill_id!r}"]
        if candidate["contract_version"] != CONTRACT_VERSION:
            return None, [f"$.contract_version: 应为 {CONTRACT_VERSION!r}"]
        if candidate["status"] == "completed" and not isinstance(candidate.get("data"), dict):
            return None, [f"$.data: completed 必须给出 {skill.output_kind} 对象"]
        return candidate, []


class ArtifactStore:
    """Thin wrapper over the host's SQLite artifact table.

    The skills never dereference anything themselves: every ``*_ref`` in a
    request must already be registered here, which is exactly the host
    obligation the packages describe.
    """

    def __init__(self, conn):
        self.conn = conn

    def register(
        self,
        task_id: str,
        skill_id: str,
        kind: str,
        data: dict[str, Any],
        artifact_id: str | None = None,
    ) -> dict[str, Any]:
        artifact_id = artifact_id or _new_id(kind.lower().replace("_", "-"))
        row = self.conn.execute(
            "SELECT COALESCE(MAX(revision),0) AS r FROM artifacts WHERE id=?", (artifact_id,)
        ).fetchone()
        revision = int(row["r"]) + 1
        self.conn.execute(
            "INSERT OR REPLACE INTO artifacts(id,task_id,skill_id,kind,revision,data,created)"
            " VALUES(?,?,?,?,?,?,?)",
            (artifact_id, task_id, skill_id, kind, revision, json.dumps(data, ensure_ascii=False), time.time()),
        )
        self.conn.commit()
        return {"artifact_id": artifact_id, "kind": kind, "revision": revision}

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["data"] = json.loads(item["data"])
        return item

    def ref(self, artifact_id: str) -> dict[str, Any]:
        """A typed reference, or raise when the artifact is not registered."""
        row = self.get(artifact_id)
        if row is None:
            raise KeyError(artifact_id)
        return {"artifact_id": row["id"], "kind": row["kind"], "revision": row["revision"]}

    def by_kind(self, task_id: str, kind: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM artifacts WHERE task_id=? AND kind=? ORDER BY created DESC",
            (task_id, kind),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["data"] = json.loads(item["data"])
            out.append(item)
        return out

    def latest(self, task_id: str, kind: str) -> dict[str, Any] | None:
        found = self.by_kind(task_id, kind)
        return found[0] if found else None

    def latest_id(self, task_id: str, kind: str) -> str | None:
        """Newest registered artifact of ``kind``, used to reuse host records."""
        row = self.conn.execute(
            "SELECT id FROM artifacts WHERE task_id=? AND kind=? ORDER BY created DESC LIMIT 1",
            (task_id, kind),
        ).fetchone()
        return row["id"] if row else None

    def ledger(self, task_id: str) -> dict[str, Any]:
        """A host-built ledger over the artifacts registered for this task.

        The contract defines ``OperationLedger`` as a host-recorded event log.
        This is an honest minimal implementation: one ``verified`` event per
        registered artifact. It is *not* a record of dispatched actions, and
        the skills are told to treat it as untrusted host input.
        """
        events = []
        for row in self.conn.execute(
            "SELECT * FROM artifacts WHERE task_id=? ORDER BY created", (task_id,)
        ).fetchall():
            events.append(
                {
                    "event_id": f"ledger-{row['id']}",
                    "event_type": "verified",
                    "occurred_at": datetime.fromtimestamp(row["created"], timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                    "artifact_ref": {
                        "artifact_id": row["id"],
                        "kind": row["kind"],
                        "revision": row["revision"],
                    },
                    "note": f"host 登记的 {row['kind']} 产物",
                }
            )
        return {
            "task_id": task_id,
            "ledger_revision": len(events),
            "events": events,
        }


def render_task(skill: SkillPackage, request: dict[str, Any]) -> str:
    """The instruction block handed to the model for one skill call.

    The skill's own SKILL.md is the operating manual; the request is the real
    wire envelope; the required-result sketch keeps the model inside
    ``$defs.<skill>Result``.
    """
    lines = [
        f"你正在执行 Skill `{skill.skill_id}`（{skill.entry.get('display_name', '')}），"
        f"版本 {skill.version}。",
        "",
        "以下是该 Skill 的完整操作规程（SKILL.md），必须严格遵守，"
        "尤其是其中「不做/不授权/不操作」的边界：",
        "",
        "<SKILL.md>",
        skill.instructions.strip(),
        "</SKILL.md>",
        "",
        "宿主已按中央契约 v1 组装好本次请求（引用均已登记，未登记的一律不得引用）：",
        "",
        "<REQUEST>",
        json.dumps(request, ensure_ascii=False, indent=2),
        "</REQUEST>",
        "",
        f"请只输出一个符合 `$defs.{skill.result_def}` 的 JSON 结果信封，字段为：",
        "contract_version, skill_id, call_id, task_id, based_on_task_revision,"
        " status, data, questions, issues, user_message。",
        "规则：",
        f"- status 取 completed | needs_user | needs_observation | blocked | failed；",
        f"- status=completed 时 data 必须是完整的 {skill.output_kind}，questions 与 issues 为空；",
        "- status=needs_user 时 questions 至少一条；needs_observation/blocked/failed 时 issues 至少一条；",
        "- 其他状态 data 用 null，不要伪造未完成的产物；",
        "- issues[].code 只能取已有枚举，retryable 默认 false；",
        "- 缺少宿主应当提供的输入时，如实返回 blocked/needs_observation 并说明，不要编造；",
        "- call_id、task_id、based_on_task_revision 直接沿用请求里的值；",
        "- 不要输出 JSON 以外的任何文字。",
    ]
    return "\n".join(lines)


def extract_json(text: str) -> Any:
    """Pull a JSON object out of a model reply (tolerating code fences)."""
    if not text:
        raise ValueError("模型返回为空")
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def build_task_snapshot(
    task_id: str,
    revision: int,
    mode: str = "self",
    paused: bool = False,
    remaining_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A contract-valid TaskSnapshot for the current task.

    ``intent_ref``/``remedy_ref``/``outcome_ref`` stay null unless the host has
    registered the matching artifact; the skills are required to treat a null
    reference as "not established yet" rather than as permission.
    """
    return {
        "task_id": task_id,
        "task_revision": revision,
        "target_item_ref": None,
        "selection_receipt_ref": None,
        "intent_ref": None,
        "remedy_ref": None,
        "outcome_ref": None,
        "mode": mode,
        "paused": paused,
        "remaining_budget": remaining_budget
        or {"actions": 3, "recovery_attempts": 1, "deadline_at": _deadline()},
        "scope_grant_refs": [],
        "pending_execution_refs": [],
        "related_artifact_refs": [],
    }


def _deadline(hours: int = 24) -> str:
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def sandbox_platform_view(
    task_id: str,
    page_text: str,
    source_ref: str,
    page_kind: str = "aftersales",
    platform_key: str = "platform-sandbox",
) -> dict[str, Any]:
    """Build a PlatformView from page text the user pasted.

    ``platform-sandbox`` has no vendored package (it is one of the three
    ``platform-*`` adapters declared in the catalog but never delivered), so
    this is the host acting as the adapter. It is a *declared synthetic*
    source: the facts are marked ``user_reported`` and the caller must not
    treat them as platform-verified. ``source_ref`` must be a registered
    artifact id (``^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$``).
    """
    return {
        "platform_key": platform_key,
        "environment": "sandbox",
        "page_kind": page_kind,
        "supported_operations": ["read_page", "navigate"],
        "unsupported_operations": [],
        "state_facts": [
            {
                "key": "page_text",
                "value": page_text[:4000],
                "evidence_refs": [source_ref],
                "certainty": "user_reported",
            }
        ],
        "rules": [],
        "controls": [],
        "expires_on_page_change": True,
    }
