$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$files = @('README.md','server.py','monitor.py','phone.py','start.cmd','start.ps1','collector','web')
$stage = Join-Path $PSScriptRoot ('.tmp/package-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force (Join-Path $stage 'docs') | Out-Null
foreach ($file in $files) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $stage -Recurse
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs/images') -Destination (Join-Path $stage 'docs') -Recurse
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'dist') | Out-Null
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath (Join-Path $PSScriptRoot 'dist/Iphonescript.zip') -Force
Write-Output 'Created dist/Iphonescript.zip (source and extension only; no local data).'
