"""End-to-end check against the real HTTP server with a fake model endpoint.

Starts a stub OpenAI-compatible server, points the app at it, then drives:
  GET  /api/status /api/skills
  POST /api/skills            (request built, no model call)
  POST /api/artifacts         (host artifact registration + contract check)
  POST /api/agent/turn        (model asks for a skill, host runs it for real)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import httpx

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
STUB_PORT = 8791
APP_PORT = 8792

CALLS = []
BAD_MODE = [False]  # switch the skill-call stub to an invalid envelope


class StubModel(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        CALLS.append(body)
        blob = json.dumps(body, ensure_ascii=False)
        if "SKILL.md" in blob:
            if BAD_MODE[0]:
                # Deliberately non-conformant envelope: the host must refuse it.
                message = {"role": "assistant", "content": json.dumps({
                    "contract_version": "1.0.0", "skill_id": "aftercare-intake",
                    "call_id": "call_bad", "task_id": "task_stub",
                    "based_on_task_revision": 0, "status": "completed",
                    "data": {"goal": "x", "unexpected_extra": 1},  # missing fields too
                    "questions": [], "issues": [], "user_message": "bad",
                })}
                return self._send(message)
            # This is a skill call: answer with a contract-shaped result envelope.
            message = {"role": "assistant", "content": json.dumps({
                "contract_version": "1.0.0", "skill_id": "aftercare-intake",
                "call_id": "call_stub", "task_id": "task_stub",
                "based_on_task_revision": 0, "status": "completed",
                "data": {"goal": "杯子有裂纹，希望退货退款",
                         "scope": "single_item_single_case", "user_facts": [],
                         "requested_outcome": "return_refund", "missing_fields": []},
                "questions": [], "issues": [], "user_message": "已整理你的诉求：退货退款。",
            }, ensure_ascii=False)}
            return self._send(message)
        has_tool_result = any(m.get("role") == "tool" for m in body.get("messages", []))
        if not has_tool_result:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_e2e_1",
                    "type": "function",
                    "function": {"name": "call_skill", "arguments": json.dumps({
                        "skill_id": "aftercare-intake",
                        "inputs": {"text": "杯子有裂纹，想退货退款"},
                    }, ensure_ascii=False)},
                }],
            }
        else:
            message = {"role": "assistant", "content": "我先确认一下你的诉求，再往下走。"}
        self._send(message)

    def _send(self, message):
        raw = json.dumps({"choices": [{"message": message}]}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def wait_for(url, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _status_for_forged_host(port: int) -> int:
    """Send a raw request with a non-local Host header and read the status."""
    import socket

    body = b'{"task_id":"x","skill_id":"aftercare-intake"}'
    request = (
        b"POST /api/skills HTTP/1.1\r\nHost: evil.example.com\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
    )
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(request)
        raw = sock.recv(4096).decode(errors="replace")
    return int(raw.split(" ", 2)[1])


def main():
    tmp_root = ROOT / "tests" / ".tmp"
    tmp_root.mkdir(exist_ok=True)
    db = Path(tempfile.mkdtemp(prefix="e2e-", dir=tmp_root)) / "e2e.sqlite3"
    stub = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), StubModel)
    Thread(target=stub.serve_forever, daemon=True).start()

    env = dict(os.environ)
    env.update({
        "AFTERCARE_DB": str(db),
        "AFTERCARE_PORT": str(APP_PORT),
        "STEP_API_KEY": "test-key-not-real",
        "STEP_MODEL": "stub-model",
        "STEP_BASE_URL": f"http://127.0.0.1:{STUB_PORT}/v1/chat/completions",
    })
    app = subprocess.Popen([PY, "-B", "-X", "utf8", "app.py"], cwd=ROOT, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{APP_PORT}"
    failures = []

    def check(label, condition, detail=""):
        print(("PASS  " if condition else "FAIL  ") + label + (f"   {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(label)

    try:
        if not wait_for(base + "/api/status"):
            raise SystemExit("app server did not start")
        status = httpx.get(base + "/api/status").json()
        check("status reports 11 loaded skills", status["skills_loaded"] == 11, status)
        check("status reports no model-side browser", status["browser_connected"] is False)
        check("status lists only platform-* as unavailable",
              sorted(status["skills_unavailable"]) == ["platform-main", "platform-sandbox",
                                                       "platform-secondary"], status)
        check("contract version is 1.0.0", status["contract_version"] == "1.0.0")

        catalog = httpx.get(base + "/api/skills").json()
        check("skill registry lists 11 packages", len(catalog["loaded"]) == 11)

        detail = httpx.get(base + "/api/skills/aftercare-intake").json()
        check("skill detail exposes SKILL.md instructions",
              "SKILL.md" not in detail["instructions"] and len(detail["instructions"]) > 200)
        check("skill detail reports 1.2.0", detail["skill_version"] == "1.2.0")

        # -- build a request without calling the model
        tid = httpx.post(base + "/api/agent/turn",
                         json={"text": "收到的杯子有裂纹，想退货退款", "mode": "self"}).json()["task_id"]
        built = httpx.post(base + "/api/skills",
                           json={"task_id": tid, "skill_id": "aftercare-intake",
                                 "inputs": {"text": "杯子有裂纹，想退货退款"},
                                 "with_model": False}).json()
        check("intake request built", built.get("status") == "request_built", built)
        check("request is contract v1.0.0",
              built["request"]["contract_version"] == "1.0.0", built.get("request"))
        check("request skill_version comes from the package",
              built["request"]["skill_version"] == "1.2.0")
        check("instructions embed the skill's own manual",
              "SKILL.md" in built["instructions"] and "REQUEST" in built["instructions"])

        # -- host artifact registration is contract-checked
        bad = httpx.post(base + "/api/artifacts",
                         json={"task_id": tid, "kind": "PlatformView",
                               "data": {"platform_key": "x"}})
        check("invalid host artifact is rejected", bad.status_code == 400, bad.text[:200])
        check("rejection lists the schema errors",
              "validation_errors" in bad.json(), bad.text[:200])
        good = httpx.post(base + "/api/artifacts",
                          json={"task_id": tid, "kind": "PlatformView", "data": {
                              "platform_key": "platform-sandbox", "environment": "sandbox",
                              "page_kind": "aftersales", "supported_operations": ["read_page"],
                              "unsupported_operations": [], "state_facts": [], "rules": [],
                              "controls": [], "expires_on_page_change": True}})
        check("valid host artifact is accepted", good.status_code == 201, good.text[:200])
        wrong_kind = httpx.post(base + "/api/artifacts",
                                json={"task_id": tid, "kind": "TaskIntent", "data": {}})
        check("skills' own outputs cannot be host-registered",
              wrong_kind.status_code == 400, wrong_kind.text[:200])

        # -- unregistered reference is refused, not fabricated
        refused = httpx.post(base + "/api/skills",
                             json={"task_id": tid, "skill_id": "aftercare-order",
                                   "inputs": {"intent": "nope-not-registered"},
                                   "with_model": False})
        check("unregistered ref refused with 409", refused.status_code == 409, refused.text[:200])
        check("refusal names the artifact",
              "nope-not-registered" in refused.text, refused.text[:200])

        # -- full agent turn: model asks for intake, host runs the real skill
        turn = httpx.post(base + "/api/agent/turn",
                          json={"text": "杯子有裂纹，想退货退款", "task_id": tid,
                                "allow_model": True}).json()
        check("turn returns a reply", bool(turn.get("reply")), turn)
        results = turn.get("skill_results") or []
        check("agent turn actually invoked a skill", len(results) == 1, turn)
        if results:
            first = results[0]
            check("invoked skill is aftercare-intake", first.get("skill_id") == "aftercare-intake")
            check("skill returned a contract-valid completed result",
                  first.get("status") == "completed", first.get("status"))
            check("completed result was stored as a TaskIntent artifact",
                  (first.get("stored_artifact") or {}).get("kind") == "TaskIntent",
                  first.get("stored_artifact"))
            check("skill result carries the built request",
                  "request" in first, sorted(first))
        check("the completed artifact is attached to the task",
              any(a["kind"] == "TaskIntent"
                  for a in httpx.get(f"{base}/api/tasks/{tid}").json()["artifacts"]))
        check("stub model was called at least twice (tool round + skill + final)",
              len(CALLS) >= 2, len(CALLS))
        check("skill instructions were sent to the model, not just a skill name",
              any("SKILL.md" in json.dumps(c, ensure_ascii=False) for c in CALLS))

        artifacts = httpx.get(f"{base}/api/tasks/{tid}").json()["artifacts"]
        kinds = sorted({a["kind"] for a in artifacts})
        check("host registered TaskSnapshot for the call", "TaskSnapshot" in kinds, kinds)
        check("UserTurn was registered as an artifact", "UserTurn" in kinds, kinds)

        # -- a non-conformant model answer must be refused and never stored
        def intent_artifacts():
            return [a for a in httpx.get(f"{base}/api/tasks/{tid}").json()["artifacts"]
                    if a["kind"] == "TaskIntent"]

        BAD_MODE[0] = True
        intent_before = len(intent_artifacts())
        bad_out = httpx.post(base + "/api/skills",
                             json={"task_id": tid, "skill_id": "aftercare-intake",
                                   "inputs": {"text": "杯子有裂纹"}}).json()
        check("invalid model result is rejected", bad_out.get("status") == "invalid_result",
              bad_out.get("status"))
        check("rejection lists contract violations",
              len(bad_out.get("validation_errors") or []) >= 2, bad_out.get("validation_errors"))
        check("no TaskIntent artifact was stored for the invalid result",
              len(intent_artifacts()) == intent_before,
              f"{intent_before} -> {len(intent_artifacts())}")
        check("stored TaskIntent is still the valid one",
              all(a["data"].get("requested_outcome") == "return_refund"
                  for a in intent_artifacts()))
        BAD_MODE[0] = False

        # -- non-local Host is refused (raw socket: httpx rewrites Host)
        check("non-local Host refused", _status_for_forged_host(APP_PORT) == 403)
    finally:
        app.terminate()
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
        err = app.stderr.read().decode(errors="replace") if app.stderr else ""
        if err.strip():
            print("\n--- server stderr ---\n" + err[:2000])
        stub.shutdown()

    print("\n" + ("ALL E2E CHECKS PASSED" if not failures
                  else f"{len(failures)} E2E FAILURES: {failures}"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
