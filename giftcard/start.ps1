$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$url = 'http://127.0.0.1:8876'
try {
    $response = Invoke-WebRequest -Uri "$url/api/state" -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200) { Start-Process $url; exit }
} catch {}
$python = (Get-Command python -ErrorAction Stop).Source
$arguments = @('server.py')
if (Test-Path -LiteralPath '../data/giftcard-messages.json') {
    $arguments += @('--import-messages', '../data/giftcard-messages.json')
}
Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Start-Sleep -Seconds 2
Start-Process $url
Write-Host "Gift Card PIN: $url"
