param([ValidateSet('start','stop','status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'user_model_preview.py'
$data = Join-Path $root '.cache\user-model-preview\unified'
if ($Action -ne 'start') { & $python $script $Action; exit $LASTEXITCODE }
# Refuse an already-running/partial instance before touching its static build.
& $python $script check
if ($LASTEXITCODE -ne 0) { throw 'Preview preflight failed; no build, data import or service started.' }
& $python $script build
if ($LASTEXITCODE -ne 0) { throw 'Unified build failed; nothing started.' }
& $python $script prepare
if ($LASTEXITCODE -ne 0) { throw 'User-model prepare failed; no services started.' }
& $python $script check
if ($LASTEXITCODE -ne 0) { throw 'Preview safety check failed; nothing started.' }
New-Item $data -ItemType Directory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Start-Process -FilePath $python -ArgumentList @('"' + $script + '"','supervise') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data "supervisor-$stamp.log") -RedirectStandardError (Join-Path $data "supervisor-$stamp-error.log") | Out-Null
$ready = $false
for ($i=0; $i -lt 35; $i++) {
    Start-Sleep 1
    try { $r=Invoke-WebRequest 'http://127.0.0.3:5183/api/v1/health' -TimeoutSec 2; if($r.StatusCode -eq 200){$ready=$true;break} } catch {}
}
if (-not $ready) { throw 'Preview not ready. Inspect timestamped logs; do not repeatedly start.' }
Write-Output 'Unified Litera ready: http://127.0.0.3:5183 (use the copied 5180 preview account or register a new isolated account).'
