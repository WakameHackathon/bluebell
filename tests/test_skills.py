"""Tests for the vendored aftercare skills integration.

Run from the repo root:  python -B -X utf8 -m unittest discover -s tests -v

Covers four things the previous hardcoded stub dispatch never did:
1. every vendored skill's own example payloads validate against the central
   contract (regression guard on the vendored copies);
2. a real contract request can be assembled for every implemented skill;
3. unregistered references are refused instead of producing fake artifacts;
4. the result envelope *and* the artifact inside ``data`` are validated.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Keep the test databases inside tests/.tmp so the repo root stays clean.
_TMP_ROOT = ROOT / "tests" / ".tmp"
_TMP_ROOT.mkdir(exist_ok=True)
_TMP = tempfile.mkdtemp(prefix="unit-", dir=_TMP_ROOT)
os.environ["AFTERCARE_DB"] = str(Path(_TMP) / "test.sqlite3")

import app  # noqa: E402
import skill_runtime as rt  # noqa: E402
from skill_schema import format_errors, is_valid  # noqa: E402

IMPLEMENTED = [
    "aftercare-intake", "aftercare-order", "aftercare-remedy", "aftercare-evidence",
    "aftercare-interact", "aftercare-verify", "aftercare-recover", "aftercare-resume",
    "aftercare-logistics", "aftercare-appeal", "aftercare-handoff",
]


class TestVendoredPackages(unittest.TestCase):
    def test_all_catalog_packages_loaded(self):
        self.assertEqual(sorted(app.REGISTRY.skills), sorted(IMPLEMENTED))
        self.assertEqual(sorted(app.REGISTRY.missing), ["platform-main", "platform-sandbox",
                                                        "platform-secondary"])

    def test_every_skill_has_skill_md_and_catalog_schema_key(self):
        for skill_id in IMPLEMENTED:
            skill = app.REGISTRY.get(skill_id)
            self.assertTrue((skill.path / "SKILL.md").is_file(), skill_id)
            self.assertIn(skill.request_def, app.CONTRACTS["$defs"], skill_id)
            self.assertIn(skill.result_def, app.CONTRACTS["$defs"], skill_id)

    def test_package_schema_file_matches_catalog_pointer(self):
        for skill_id in IMPLEMENTED:
            skill = app.REGISTRY.get(skill_id)
            rel = skill.entry.get("schema")
            if not rel:
                continue  # aftercare-handoff ships no schema excerpt
            self.assertTrue((skill.path / rel).is_file(), f"{skill_id}: {rel} missing")

    def test_vendored_examples_still_validate_against_central_contract(self):
        """Every wire example a package ships must pass the central contract.

        Most packages ship no ``examples/`` directory in the loadable zip, so
        the full upstream corpus is picked up from the design clone when it is
        present. Both locations are checked; the test asserts on whatever it
        found so it stays honest when run from a bare checkout.
        """
        sources = list((ROOT / "skills").glob("*/examples/*.json"))
        upstream = Path(os.environ.get(
            "AFTERCARE_UPSTREAM", str(ROOT.parent / "NVIDIA_Skill_Design")))
        if upstream.is_dir():
            # Upstream keeps the wire examples next to each skill repo's zip.
            for pattern in ("aftercare-*/examples/*.json",
                            "aftercare-*/_extracted/examples/*.json"):
                sources += list(upstream.glob(pattern))
        checked = 0
        for path in sorted(set(sources)):
            if path.name != "request.json" and not path.name.startswith("result"):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue  # not a wire example (manifest, schema, config)
            body = payload.get("body", payload) if isinstance(payload, dict) else payload
            if not isinstance(body, dict):
                continue
            skill_id = body.get("skill_id")
            if skill_id not in IMPLEMENTED:
                continue
            if "status" in body:
                definition = app.REGISTRY.get(skill_id).result_def
            elif "expected_task_revision" in body:
                definition = app.REGISTRY.get(skill_id).request_def
            else:
                continue
            errors = format_errors(app.CONTRACTS["$defs"][definition], body, app.CONTRACTS)
            self.assertEqual(errors, [], f"{path.name}: {errors[:3]}")
            checked += 1
        self.assertGreaterEqual(
            checked, 20,
            f"expected to exercise the shipped examples, only found {checked}")


class TestRequestAssembly(unittest.TestCase):
    def setUp(self):
        self.tid = app.new_task("测试任务", "self")

    def _seed(self, kind: str, data: dict) -> str:
        return app.store().register(self.tid, "host", kind, data)["artifact_id"]

    def test_intake_request_builds_and_validates(self):
        out = app.run_skill(self.tid, "aftercare-intake",
                            {"text": "我收到的杯子有裂纹，想退回去"}, with_model=False)
        self.assertEqual(out["status"], "request_built")
        self.assertEqual(out["skill_version"], "1.2.0")
        request = out["request"]
        self.assertEqual(request["contract_version"], "1.0.0")
        self.assertEqual(request["skill_id"], "aftercare-intake")
        self.assertIn("user_turn", request["inputs"])
        turn_ref = request["inputs"]["user_turn"]
        self.assertEqual(turn_ref["kind"], "UserTurn")
        turn = app.store().get(turn_ref["artifact_id"])["data"]
        self.assertEqual(turn["text"], "我收到的杯子有裂纹，想退回去")
        self.assertEqual(turn["task_id"], self.tid)
        self.assertEqual(
            format_errors(app.CONTRACTS["$defs"]["aftercare-intakeRequest"], request,
                          app.CONTRACTS), [])

    def test_every_skill_assembles_a_contract_valid_request(self):
        """Seed the host artifacts each skill needs, then build its request."""
        page = "订单 2024 显示：仅退款 / 退货退款，7 天内可申请。"
        for skill_id in IMPLEMENTED:
            with self.subTest(skill=skill_id):
                tid = app.new_task(f"task-{skill_id}", "self")
                seed = _Seeder(tid)
                args = seed.args_for(skill_id, page)
                out = app.run_skill(tid, skill_id, args, page_text=page, with_model=False)
                self.assertEqual(out["status"], "request_built", out.get("user_message"))
                request = out["request"]
                errors = format_errors(
                    app.CONTRACTS["$defs"][app.REGISTRY.get(skill_id).request_def],
                    request, app.CONTRACTS)
                self.assertEqual(errors, [], f"{skill_id}: {errors[:4]}")

    def test_unregistered_reference_is_refused(self):
        with self.assertRaises(app.HTTPError) as ctx:
            app.run_skill(self.tid, "aftercare-order",
                          {"intent": "artifact-that-does-not-exist"}, with_model=False)
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn("artifact-that-does-not-exist", ctx.exception.detail)
        self.assertEqual(
            ctx.exception.extra["unregistered_artifacts"], ["artifact-that-does-not-exist"])

    def test_wrong_artifact_kind_is_not_silently_accepted(self):
        bad = self._seed("TaskIntent", {
            "goal": "x", "scope": "single_item_single_case", "user_facts": [],
            "requested_outcome": "undecided", "missing_fields": [],
        })
        with self.assertRaises(app.HTTPError) as ctx:
            app.run_skill(self.tid, "aftercare-order", {"intent": bad}, with_model=False)
        self.assertEqual(ctx.exception.status, 409)

    def test_platform_view_autobuilt_from_pasted_page_text(self):
        out = app.run_skill(self.tid, "aftercare-verify", {}, page_text="状态：待商家处理",
                            with_model=False)
        self.assertEqual(out["status"], "request_built")
        ref = out["request"]["inputs"]["platform_view"]
        stored = app.store().get(ref["artifact_id"])
        self.assertEqual(stored["kind"], "PlatformView")
        self.assertEqual(stored["data"]["environment"], "sandbox")
        self.assertEqual(stored["data"]["state_facts"][0]["certainty"], "user_reported")

    def test_ledger_is_registered_and_referenced_not_inlined(self):
        out = app.run_skill(self.tid, "aftercare-verify", {}, page_text="状态：待商家处理",
                            with_model=False)
        ref = out["request"]["inputs"]["ledger"]
        self.assertEqual(ref["kind"], "OperationLedger")
        stored = app.store().get(ref["artifact_id"])
        ledger = stored["data"]
        self.assertEqual(ledger["task_id"], self.tid)
        self.assertGreaterEqual(len(ledger["events"]), 1)
        self.assertEqual(ledger["ledger_revision"], len(ledger["events"]))

    def test_inputs_are_references_except_declared_envelope_literals(self):
        """Guards the contract rule: every input is a ref or a declared literal.

        ``aftercare-interact.goal_step`` is the one literal object (``Step`` has
        no ``$defs`` entry), so it is allowed to carry Step's own fields.
        """
        allowed_literals = {"goal_step"}
        for skill_id in IMPLEMENTED:
            with self.subTest(skill=skill_id):
                tid = app.new_task(f"shapes-{skill_id}", "self")
                args = _Seeder(tid).args_for(skill_id, "页面文字")
                out = app.run_skill(tid, skill_id, args, page_text="页面文字",
                                    with_model=False)
                for name, value in out["request"]["inputs"].items():
                    if name in allowed_literals:
                        self.assertEqual(set(value), set(app.REGISTRY.defs["Step"]["required"]),
                                         f"{skill_id}.{name} must be a Step record")
                        continue
                    if isinstance(value, dict):
                        self.assertEqual(set(value), {"artifact_id", "kind", "revision"},
                                         f"{skill_id}.{name} must be a reference")
                    elif isinstance(value, list) and value and isinstance(value[0], dict):
                        self.assertEqual(set(value[0]), {"artifact_id", "kind", "revision"},
                                         f"{skill_id}.{name}[] must be a reference")


class _Seeder:
    """Register the host artifacts a given skill's inputs need."""

    def __init__(self, tid: str):
        self.tid = tid
        self.store = app.store()

    def _reg(self, kind: str, data: dict) -> str:
        return self.store.register(self.tid, "host", kind, data)["artifact_id"]

    def args_for(self, skill_id: str, page: str) -> dict:
        args: dict = {}
        if skill_id == "aftercare-intake":
            return {"text": "收到的杯子有裂纹，想退货退款"}
        intent = self._reg("TaskIntent", {
            "goal": "杯子有裂纹，希望退货退款", "scope": "single_item_single_case",
            "user_facts": [], "requested_outcome": "return_refund", "missing_fields": [],
        })
        order = self._reg("OrderSelection", {
            "candidates": [], "selected_item_ref": "item-1",
            "selection_receipt_ref": None, "lookup_steps": [],
        })
        remedy = self._reg("RemedyPlan", {
            "options": [], "recommended_option_id": None, "chosen_option_id": None,
            "choice_receipt_ref": None, "material_requirements": [], "next_steps": [],
        })
        outcome = self._reg("OutcomeReport", {
            "platform_state": "unknown", "effect_result": "unknown", "stage_complete": False,
            "case_terminal": False, "business_result": "unknown",
            "actual_receipt_confirmed": "unknown", "evidence_refs": [], "user_todos": [],
        })
        evidence = self._reg("EvidenceBundle", {
            "original_file_refs": [], "derived_files": [], "requirement_checks": [],
            "capture_guidance": [], "statement_draft": None, "review_receipt_ref": None,
        })
        failure = self._reg("FailureEvent", {
            "failure_id": "fail-1", "task_id": self.tid, "call_ref": "call-1",
            "execution_ref": None, "dispatch_state": "not_sent", "code": "tool_failure",
            "observation_ref": None, "occurred_at": rt._now(),
        })
        snapshot = self._reg("TaskSnapshot", rt.build_task_snapshot(self.tid, 0))
        decision = self._reg("UserDecision", {
            "decision_id": "dec-1", "task_id": self.tid, "user_event_ref": "turn-1",
            "decision_kind": "select_item", "subject_ref": "candidates-v1",
            "selected_value_ref": "item-1", "based_on_task_revision": 0,
            "recorded_at": rt._now(),
        })
        if skill_id == "aftercare-order":
            args = {"intent": intent}
        elif skill_id == "aftercare-remedy":
            args = {"intent": intent, "order": order}
        elif skill_id == "aftercare-evidence":
            args = {"remedy": remedy, "approved_file_refs": []}
        elif skill_id == "aftercare-interact":
            args = {"source_artifacts": [intent, order, remedy]}
        elif skill_id == "aftercare-recover":
            args = {"failure": failure}
        elif skill_id == "aftercare-resume":
            args = {"saved_task": snapshot, "current_outcome": outcome}
        elif skill_id == "aftercare-logistics":
            args = {"order": order, "remedy": remedy, "outcome": outcome,
                    "user_decision": decision}
        elif skill_id == "aftercare-appeal":
            args = {"outcome": outcome, "evidence": evidence}
        elif skill_id == "aftercare-handoff":
            args = {"outcome": outcome, "evidence": evidence}
        return args


class TestResultValidation(unittest.TestCase):
    def setUp(self):
        self.tid = app.new_task("校验任务", "self")

    def test_valid_result_is_registered_as_an_artifact(self):
        skill = app.REGISTRY.get("aftercare-intake")
        result = {
            "contract_version": "1.0.0", "skill_id": "aftercare-intake",
            "call_id": "call-1", "task_id": self.tid, "based_on_task_revision": 0,
            "status": "completed",
            "data": {"goal": "退货退款", "scope": "single_item_single_case", "user_facts": [],
                     "requested_outcome": "return_refund", "missing_fields": []},
            "questions": [], "issues": [], "user_message": "已整理你的诉求。",
        }
        got, errors = app.REGISTRY.validate_result(skill, result)
        self.assertEqual(errors, [])
        self.assertIsNotNone(got)
        ref = app.store().register(self.tid, "aftercare-intake", skill.output_kind, got["data"])
        self.assertEqual(app.store().get(ref["artifact_id"])["kind"], "TaskIntent")

    def test_result_with_incomplete_artifact_is_rejected(self):
        """The old app.py returned exactly this shape for 13 of 14 skills."""
        skill = app.REGISTRY.get("aftercare-verify")
        bogus = {
            "contract_version": "1.0.0", "skill_id": "aftercare-verify",
            "call_id": "call-2", "task_id": self.tid, "based_on_task_revision": 0,
            "status": "completed",
            "data": {"actions": [], "page_evidence": "", "execution_enabled": False},
            "questions": [], "issues": [], "user_message": "ok",
        }
        got, errors = app.REGISTRY.validate_result(skill, bogus)
        self.assertIsNone(got)
        self.assertTrue(any("missing required property" in e for e in errors))
        self.assertTrue(any("unexpected property" in e for e in errors))

    def test_needs_user_requires_a_question(self):
        skill = app.REGISTRY.get("aftercare-intake")
        result = {
            "contract_version": "1.0.0", "skill_id": "aftercare-intake",
            "call_id": "call-3", "task_id": self.tid, "based_on_task_revision": 0,
            "status": "needs_user", "data": None, "questions": [], "issues": [],
            "user_message": "请补充信息。",
        }
        got, errors = app.REGISTRY.validate_result(skill, result)
        self.assertIsNone(got, "needs_user without questions must be rejected")
        self.assertNotEqual(errors, [])

    def test_wrong_skill_id_is_rejected(self):
        skill = app.REGISTRY.get("aftercare-intake")
        result = {
            "contract_version": "1.0.0", "skill_id": "aftercare-order",
            "call_id": "call-4", "task_id": self.tid, "based_on_task_revision": 0,
            "status": "failed", "data": None, "questions": [],
            "issues": [{"code": "contract_error", "message": "x", "retryable": False,
                        "evidence_refs": []}], "user_message": "x",
        }
        got, errors = app.REGISTRY.validate_result(skill, result)
        self.assertIsNone(got)


class TestSchemaValidator(unittest.TestCase):
    def test_extra_property_is_rejected(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}},
                  "required": ["a"], "additionalProperties": False}
        self.assertTrue(is_valid(schema, {"a": "x"}))
        self.assertFalse(is_valid(schema, {"a": "x", "b": 1}))

    def test_conditional_status_rules(self):
        schema = {"type": "object", "properties": {"s": {"type": "string"}},
                  "required": ["s"],
                  "allOf": [{"if": {"properties": {"s": {"const": "completed"}}},
                             "then": {"properties": {"extra": {"type": "string"}},
                                      "required": ["extra"]}}]}
        self.assertFalse(is_valid(schema, {"s": "completed"}))
        self.assertTrue(is_valid(schema, {"s": "completed", "extra": "y"}))
        self.assertTrue(is_valid(schema, {"s": "draft"}))

    def test_bool_is_not_an_integer(self):
        self.assertFalse(is_valid({"type": "integer"}, True))
        self.assertTrue(is_valid({"type": "integer"}, 3))

    def test_local_ref_resolution(self):
        schema = {"$defs": {"X": {"type": "string", "minLength": 2}},
                  "$ref": "#/$defs/X"}
        self.assertTrue(is_valid(schema, "ab"))
        self.assertFalse(is_valid(schema, "a"))


class TestHttpEndpoints(unittest.TestCase):
    def test_register_host_artifact_validates_against_contract(self):
        tid = app.new_task("http", "self")
        out = app.register_artifact({
            "task_id": tid, "kind": "PlatformView",
            "data": rt.sandbox_platform_view(tid, "页面文字", "src-1"),
        })
        self.assertEqual(out["kind"], "PlatformView")
        with self.assertRaises(app.HTTPError):
            app.register_artifact({
                "task_id": tid, "kind": "PlatformView", "data": {"platform_key": "only-this"},
            })

    def test_only_host_kinds_may_be_registered(self):
        tid = app.new_task("http2", "self")
        with self.assertRaises(app.HTTPError):
            app.register_artifact({"task_id": tid, "kind": "TaskIntent", "data": {}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
