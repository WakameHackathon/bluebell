#!/usr/bin/env python3
"""Deterministic structural and reference-scope checks for synthetic HandoffDraft payloads."""
import argparse, json, re, sys
from pathlib import Path
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISSUES = {"missing_input","stale_observation","target_unconfirmed","policy_unknown","needs_login","needs_consent","unsupported","ambiguous_result","budget_exhausted","contract_error","tool_failure","user_paused"}
BASE = {"contract_version","skill_id","call_id","task_id","based_on_task_revision","status","data","questions","issues","user_message"}
DRAFT = {"official_channel_ref","summary","timeline_evidence_refs","unresolved_questions","message_draft","file_refs"}
def check(payload, allowed_refs=None):
    errors=[]
    if not isinstance(payload,dict) or set(payload)!=BASE: return ["result fields must exactly match aftercare-handoffResult"]
    if payload["contract_version"]!="1.0.0" or payload["skill_id"]!="aftercare-handoff": errors.append("contract_version/skill_id mismatch")
    if not all(isinstance(payload[k],str) and payload[k] for k in ("call_id","task_id","user_message")): errors.append("identity and user_message must be nonempty strings")
    if not isinstance(payload["based_on_task_revision"],int) or payload["based_on_task_revision"]<0: errors.append("invalid based_on_task_revision")
    st=payload["status"]
    if st not in {"completed","needs_user","needs_observation","blocked","failed"}: errors.append("invalid status")
    qs,issues=payload["questions"],payload["issues"]
    if not isinstance(qs,list) or not isinstance(issues,list): errors.append("questions/issues must be arrays"); qs=[]; issues=[]
    if st=="completed" and (not isinstance(payload["data"],dict) or qs or issues): errors.append("completed requires data and empty questions/issues")
    if st=="needs_user" and not qs: errors.append("needs_user requires a question")
    if st in {"needs_observation","blocked","failed"} and not issues: errors.append(f"{st} requires an issue")
    for q in qs:
        if not isinstance(q,dict) or set(q)!={"question_id","text","choices"} or not isinstance(q.get("question_id"),str) or not ID.fullmatch(q.get("question_id","")) or not isinstance(q.get("text"),str) or not q.get("text") or not isinstance(q.get("choices"),list): errors.append("invalid Question shape")
    for i in issues:
        if not isinstance(i,dict) or set(i)!={"code","message","retryable","evidence_refs"} or i.get("code") not in ISSUES or not isinstance(i.get("message"),str) or not i.get("message") or not isinstance(i.get("retryable"),bool) or not isinstance(i.get("evidence_refs"),list): errors.append("invalid Issue shape")
    d=payload["data"]
    if isinstance(d,dict):
        if set(d)!=DRAFT: errors.append("data must have exactly the six HandoffDraft fields")
        else:
            if d["official_channel_ref"] is not None and (not isinstance(d["official_channel_ref"],str) or not ID.fullmatch(d["official_channel_ref"])): errors.append("invalid official_channel_ref")
            for key in ("summary","message_draft"):
                if not isinstance(d[key],str) or not d[key].strip(): errors.append(f"{key} must be nonempty")
            for key in ("timeline_evidence_refs","unresolved_questions","file_refs"):
                if not isinstance(d[key],list): errors.append(f"{key} must be an array")
                elif key!="unresolved_questions" and any(not isinstance(x,str) or not ID.fullmatch(x) for x in d[key]): errors.append(f"invalid reference in {key}")
                elif key=="unresolved_questions" and any(not isinstance(x,str) or not x.strip() for x in d[key]): errors.append("unresolved_questions contains empty text")
            if allowed_refs is not None:
                for key in ("timeline_evidence_refs","file_refs"):
                    for ref in d[key]:
                        if ref not in allowed_refs: errors.append(f"{key} reference not in current-task allowlist: {ref}")
                ref=d["official_channel_ref"]
                if ref is not None and ref not in allowed_refs: errors.append("official_channel_ref not in current-task allowlist")
    elif st=="completed": errors.append("completed data must be HandoffDraft")
    return errors
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("payload",type=Path); ap.add_argument("--allowlist",type=Path,help="JSON array of refs independently resolved by the host")
    a=ap.parse_args()
    try:
        obj=json.loads(a.payload.read_text(encoding="utf-8")); allow=json.loads(a.allowlist.read_text(encoding="utf-8")) if a.allowlist else None
    except Exception as e: print(f"input error: {e}",file=sys.stderr); return 2
    errors=check(obj,allow)
    if errors: print("INVALID\n"+"\n".join("- "+e for e in errors)); return 1
    print("STRUCTURE_VALID (does not prove truth, authorization, channel authenticity, attachment safety, or successful handoff)"); return 0
if __name__=="__main__": raise SystemExit(main())
