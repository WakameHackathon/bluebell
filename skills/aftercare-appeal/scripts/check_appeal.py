#!/usr/bin/env python3
"""Deterministic structural and cross-reference checks for AppealDraft fixtures.

This is a package-side lint helper, not a host trust, authorization, or ledger gate.
It intentionally accepts already-resolved IDs supplied by the caller.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISSUE_CODES = {
    "missing_input", "stale_observation", "target_unconfirmed", "policy_unknown",
    "needs_login", "needs_consent", "unsupported", "ambiguous_result",
    "budget_exhausted", "contract_error", "tool_failure", "user_paused",
}
STATUSES = {"completed", "needs_user", "needs_observation", "blocked", "failed"}
RECOMMENDATIONS = {"prepare", "collect_more", "handoff", "stop"}


def _id(value: Any) -> bool:
    return isinstance(value, str) and ID.fullmatch(value) is not None


def validate_request(req: dict) -> list[str]:
    errors: list[str] = []
    required = {"contract_version", "skill_id", "skill_version", "call_id", "task_id",
                "expected_task_revision", "mode", "task_snapshot", "inputs"}
    if set(req) != required:
        errors.append("request_fields")
    if req.get("contract_version") != "1.0.0" or req.get("skill_id") != "aftercare-appeal":
        errors.append("request_contract_identity")
    if not isinstance(req.get("skill_version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", req.get("skill_version", "")):
        errors.append("skill_version")
    if not _id(req.get("call_id")) or not _id(req.get("task_id")):
        errors.append("request_ids")
    if not isinstance(req.get("expected_task_revision"), int) or req.get("expected_task_revision", -1) < 0:
        errors.append("task_revision")
    if req.get("mode") not in {"self", "guided", "auto"}:
        errors.append("mode")
    if not _ref(req.get("task_snapshot"), "TaskSnapshot"):
        errors.append("task_snapshot_ref")
    inputs = req.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"outcome", "platform_view", "evidence", "ledger"}:
        errors.append("input_fields")
    else:
        for key, kind in (("outcome", "OutcomeReport"), ("platform_view", "PlatformView"),
                          ("evidence", "EvidenceBundle"), ("ledger", "OperationLedger")):
            if not _ref(inputs.get(key), kind):
                errors.append(f"{key}_ref")
    return errors


def _ref(ref: Any, kind: str) -> bool:
    return (isinstance(ref, dict) and set(ref) == {"artifact_id", "kind", "revision"}
            and _id(ref.get("artifact_id")) and ref.get("kind") == kind
            and isinstance(ref.get("revision"), int) and ref.get("revision", -1) >= 0)


def validate_result(result: dict, request: dict | None = None,
                    registered_refs: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    fields = {"contract_version", "skill_id", "call_id", "task_id", "based_on_task_revision",
              "status", "data", "questions", "issues", "user_message"}
    if set(result) != fields:
        errors.append("result_fields")
    if result.get("contract_version") != "1.0.0" or result.get("skill_id") != "aftercare-appeal":
        errors.append("result_contract_identity")
    if request and any(result.get(a) != b for a, b in (("call_id", request.get("call_id")), ("task_id", request.get("task_id")))):
        errors.append("request_result_identity_mismatch")
    if result.get("status") not in STATUSES:
        errors.append("status")
    if not isinstance(result.get("based_on_task_revision"), int) or result.get("based_on_task_revision", -1) < 0:
        errors.append("based_on_task_revision")
    questions, issues = result.get("questions"), result.get("issues")
    if not isinstance(questions, list) or not isinstance(issues, list) or not isinstance(result.get("user_message"), str) or not result.get("user_message"):
        errors.append("result_envelope_values")
        questions, issues = [], []
    status = result.get("status")
    if status == "completed" and (not isinstance(result.get("data"), dict) or questions or issues):
        errors.append("completed_shape")
    if status == "needs_user" and not questions:
        errors.append("needs_user_question_required")
    if status in {"needs_observation", "blocked", "failed"} and not issues:
        errors.append("issue_required")
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("code") not in ISSUE_CODES or not isinstance(issue.get("message"), str) or not isinstance(issue.get("retryable"), bool) or not isinstance(issue.get("evidence_refs"), list):
            errors.append("issue_shape")
    data = result.get("data")
    if data is None:  # Allowed by central schema for non-completed; stricter host policy may differ.
        return errors
    if not isinstance(data, dict) or set(data) != {"reason_evidence_refs", "grounds", "draft_text", "file_refs", "missing_evidence", "available_route_refs", "recommendation"}:
        errors.append("appeal_draft_shape")
        return errors
    if data.get("recommendation") not in RECOMMENDATIONS:
        errors.append("recommendation")
    if data.get("draft_text") is not None and (not isinstance(data.get("draft_text"), str) or not data.get("draft_text")):
        errors.append("draft_text")
    for field in ("reason_evidence_refs", "file_refs", "available_route_refs"):
        vals = data.get(field)
        if not isinstance(vals, list) or any(not _id(v) for v in vals):
            errors.append(f"{field}_shape")
        elif registered_refs is not None and any(v not in registered_refs for v in vals):
            errors.append(f"{field}_not_registered")
    if not isinstance(data.get("missing_evidence"), list) or any(not isinstance(v, str) or not v for v in data.get("missing_evidence", [])):
        errors.append("missing_evidence_shape")
    if not isinstance(data.get("grounds"), list):
        errors.append("grounds_shape")
    else:
        for g in data["grounds"]:
            if not isinstance(g, dict) or set(g) != {"key", "value", "evidence_refs", "certainty"} or not _id(g.get("key")) or not isinstance(g.get("value"), str) or not g.get("value") or g.get("certainty") not in {"observed", "user_reported", "inferred"} or not isinstance(g.get("evidence_refs"), list) or not g.get("evidence_refs") or any(not _id(v) for v in g.get("evidence_refs", [])):
                errors.append("fact_shape")
                continue
            if g.get("certainty") == "inferred" and data.get("draft_text") and any(t in data["draft_text"] for t in ("我亲眼", "我拍摄", "我收到", "我购买")):
                # Heuristic lint only: humans/host must validate actual claim provenance.
                errors.append("inferred_claim_wording_review")
            if registered_refs is not None and any(v not in registered_refs for v in g["evidence_refs"]):
                errors.append("ground_evidence_not_registered")
    return sorted(set(errors))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_appeal.py <json-file>", file=sys.stderr)
        return 2
    p = Path(sys.argv[1])
    payload = json.loads(p.read_text(encoding="utf-8"))
    if "message_type" in payload:
        body = payload.get("body", {})
        errors = validate_request(body) if payload.get("message_type") == "request" else validate_result(body)
    else:
        errors = validate_result(payload)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
