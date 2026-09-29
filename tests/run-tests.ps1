# Runs the skills integration tests.
#
# Uses the repo virtualenv when it exists, otherwise whatever "python" is on
# PATH. The only third-party dependency is httpx, which app.py needs anyway, so
# create the venv first (see README) if the tests fail to import it.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }

Push-Location $root
try {
  Write-Host "=== unit tests ===" -ForegroundColor Cyan
  & $python -B -X utf8 -m unittest discover -s tests -p "test_*.py"
  $unit = $LASTEXITCODE
  if ($unit -ne 0) {
    Write-Host "`nIf the failure is a missing httpx: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit $unit
  }

  Write-Host "`n=== end-to-end HTTP tests (stub model) ===" -ForegroundColor Cyan
  & $python -B -X utf8 "tests\_e2e_http.py"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  # Needs the documented default port 8766 to be free.
  Write-Host "`n=== README startup smoke test ===" -ForegroundColor Cyan
  & $python -B -X utf8 "tests\_smoke_readme.py"
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
