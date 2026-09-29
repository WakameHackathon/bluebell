"""Smoke-test the exact path a reader of README.md would take.

Starts ``app.py`` on the documented default port with the documented command and
no environment overrides, then checks the served UI and the skill registry.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
failures = []


def check(label, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label + (f"   {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


def get(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.read()


def release_stale_aftercare_servers(port):
    """Stop leftover ``app.py`` servers holding the port.

    Earlier runs in this project leave servers behind, and a foreign server on
    the port makes this test meaningless: it would probe a different code
    revision. Only processes whose command line is an ``app.py`` are stopped;
    anything else means the port is genuinely occupied by someone else.
    """
    import subprocess as sp

    if os.name != "nt":
        return "unknown-owner"
    script = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue"
        " | Select-Object -ExpandProperty OwningProcess -Unique"
    )
    try:
        out = sp.run(["powershell", "-NoProfile", "-Command", script],
                     capture_output=True, text=True, timeout=30).stdout
    except (OSError, sp.SubprocessError):
        return "unknown-owner"
    for pid in [p.strip() for p in out.split() if p.strip().isdigit()]:
        try:
            cmd = sp.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, sp.SubprocessError):
            cmd = ""
        if "app.py" not in cmd:
            return f"foreign process {pid}: {cmd[:120]}"
        print(f"  stopping stale aftercare server on port {port} (pid {pid})")
        sp.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True, timeout=30)
        time.sleep(1.0)
    return None


def wait_for_own_server(port, timeout=30):
    """Wait until *this* app answers, not any process that happens to hold the port.

    A bare port check is not enough: a leftover server from an earlier run will
    accept the connection while serving a different code revision, which is how
    this test first produced misleading results. The status payload must carry
    the contract version this revision serves.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as r:
                data = json.loads(r.read())
            if "contract_version" in data and "skills_loaded" in data:
                return True
            print(f"  port {port} answers but with a foreign payload: {data}")
            return False
        except OSError:
            time.sleep(0.25)
        except (ValueError, json.JSONDecodeError):
            time.sleep(0.25)
    return False


def main():
    # app.py writes aftercare.sqlite3 next to itself by default; point it at a
    # temp file so this smoke test leaves the working tree untouched.
    tmp = Path(tempfile.mkdtemp(prefix="readme-", dir=ROOT / "tests" / ".tmp"))
    env = dict(os.environ)
    env["AFTERCARE_DB"] = str(tmp / "smoke.sqlite3")
    env.pop("STEP_API_KEY", None)  # documented local mode, no key configured
    env.pop("AFTERCARE_PORT", None)  # exercise the default port

    blocked = release_stale_aftercare_servers(PORT)
    check(f"port {PORT} is available for the documented startup", blocked is None, blocked)

    proc = subprocess.Popen([PY, "-B", "-X", "utf8", "app.py"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        check("server answers on the documented default port 8766 with our payload",
              wait_for_own_server(PORT))
        if failures:
            return 1
        status, body = get("/")
        html = body.decode("utf-8", errors="replace")
        check("/ serves the landing page", status == 200 and "<html" in html.lower())
        # index.html is a landing page: the chat UI lives in the extension, so
        # it must point the reader at loading the unpacked extension.
        check("landing page explains loading the extension",
              "chrome://extensions" in html and "extension" in html, html[:300])

        status, body = get("/api/status")
        data = json.loads(body)
        check("status is local mode without a key", data["model_configured"] is False, data)
        check("status reports 11 of 14 skills loaded",
              data["skills_loaded"] == 11 and data["skills_total"] == 14, data)
        check("status exposes the skills list the UI counts",
              isinstance(data["skills"], list) and len(data["skills"]) == 11)

        status, body = get("/api/skills")
        catalog = json.loads(body)
        ids = sorted(s["skill_id"] for s in catalog["loaded"])
        check("all 11 aftercare skills are registered", len(ids) == 11, ids)
        check("every loaded skill reports an output artifact kind",
              all(s["output_kind"] for s in catalog["loaded"]))

        status, body = get("/api/skills/aftercare-handoff")
        detail = json.loads(body)
        check("skill detail serves its SKILL.md body",
              len(detail["instructions"]) > 200, len(detail.get("instructions", "")))
    finally:
        proc.terminate()
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        banner = (out or b"").decode(errors="replace")
        print("\n--- app.py stdout ---\n" + banner.strip())
        if (err or b"").strip():
            print("--- app.py stderr ---\n" + err.decode(errors="replace")[:1500])

    print("\n" + ("README PATH WORKS" if not failures else f"FAILURES: {failures}"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
