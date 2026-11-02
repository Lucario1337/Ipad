# Laedt das KI-Programm llama.cpp (llama-server.exe) fuer Windows von GitHub.
param([string]$Ziel)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$rel = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest' -Headers @{ 'User-Agent' = 'USB-KI' }
$asset = $rel.assets | Where-Object { $_.name -like '*bin-win-cpu-x64.zip' } | Select-Object -First 1
if (-not $asset) { $asset = $rel.assets | Where-Object { $_.name -like '*bin-win-avx2-x64.zip' } | Select-Object -First 1 }
if (-not $asset) { throw 'Keine passende Windows-Datei im neuesten llama.cpp-Release gefunden.' }
Write-Host ('Lade ' + $asset.name + ' ...')
$zip = Join-Path $Ziel 'llama.zip'
Invoke-WebRequest $asset.browser_download_url -OutFile $zip -Headers @{ 'User-Agent' = 'USB-KI' }
$ordner = Join-Path $Ziel 'llama'
if (Test-Path $ordner) { Remove-Item $ordner -Recurse -Force }
Expand-Archive $zip $ordner -Force
Remove-Item $zip
$exe = Get-ChildItem $ordner -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
if (-not $exe) { throw 'llama-server.exe fehlt nach dem Entpacken (Virenscanner?).' }
Write-Host ('OK: ' + $exe.FullName)
