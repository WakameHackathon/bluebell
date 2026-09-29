# Runs the skills integration tests. Uses the repo virtualenv when present,
# otherwise whatever "python" is on PATH (the only third-party dependency is
# httpx, which app.py needs anyway).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }

Write-Host "=== unit tests ===" -ForegroundColor Cyan
& $python -B -X utf8 -m unittest discover -s "$PSScriptRoot" -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== end-to-end HTTP tests (stub model) ===" -ForegroundColor Cyan
& $python -B -X utf8 "$PSScriptRoot\_e2e_http.py"
exit $LASTEXITCODE
