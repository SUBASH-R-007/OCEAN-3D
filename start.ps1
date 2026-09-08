$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run python -m venv .venv and pip install -r requirements.lock.txt first. See README.md.' }
$taskApiLog = Join-Path $PSScriptRoot 'api.log'
$taskApiError = Join-Path $PSScriptRoot 'api-error.log'
$env:OCEAN_HOST = '127.0.0.1'
$env:OCEAN_PORT = '8000'
$env:OCEAN_MODE = 'writable'
$env:OCEAN_WORKERS = '1'
if (-not $env:OCEAN_SYNC_ENABLED) { $env:OCEAN_SYNC_ENABLED = 'true' }
$taskApiProcess = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -ArgumentList @('-m','backend.server') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskApiLog -RedirectStandardError $taskApiError
try {
  Set-Location -LiteralPath (Join-Path $PSScriptRoot 'web')
  npm.cmd run dev:selfhost
} finally {
  if (-not $taskApiProcess.HasExited) { Stop-Process -Id $taskApiProcess.Id }
}
