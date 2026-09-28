$ErrorActionPreference = "Stop"
if (-not $env:STEP_API_KEY) {
  $secureKey = Read-Host "阶跃星辰密钥（回车跳过，使用本地模式）" -AsSecureString
  if ($secureKey.Length -gt 0) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try { $env:STEP_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  }
}
python app.py
