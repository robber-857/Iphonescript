$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$files = @('README.md','server.py','monitor.py','phone.py','start.cmd','start.ps1','collector','web')
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'dist') | Out-Null
Compress-Archive -LiteralPath $files -DestinationPath (Join-Path $PSScriptRoot 'dist/Iphonescript.zip') -Force
Write-Output 'Created dist/Iphonescript.zip (source and extension only; no local data).'
