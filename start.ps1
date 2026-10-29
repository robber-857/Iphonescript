$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$monitorUrl = 'http://127.0.0.1:8765'
try {
    $existing = Invoke-RestMethod "$monitorUrl/api/state" -TimeoutSec 2
    if ($existing.variants) {
        Start-Process $monitorUrl
        exit 0
    }
} catch {}
$pythonPath = (Get-Command python -ErrorAction Stop).Source
New-Item -ItemType Directory -Force "$PSScriptRoot/.tmp" | Out-Null
$env:TEMP = "$PSScriptRoot/.tmp"
$env:TMP = "$PSScriptRoot/.tmp"
Start-Process -FilePath $pythonPath -ArgumentList 'server.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot/data-server.log" -RedirectStandardError "$PSScriptRoot/data-server-error.log"
for ($i=0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $ready = Invoke-RestMethod "$monitorUrl/api/state" -TimeoutSec 1
        if ($ready.variants) {
            Start-Process $monitorUrl
            exit 0
        }
    } catch {}
}
throw 'Backend did not start. See data-server-error.log.'
