param([ValidateSet('start','stop','status')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'local_site.py'
$data = Join-Path $root '.cache\local-site'
if ($Action -eq 'stop') { & $python $script stop; exit $LASTEXITCODE }
if ($Action -eq 'status') {
    foreach ($url in @('http://127.0.0.1:8002/api/v1/health','http://127.0.0.1:5177/api/v1/health')) {
        try { $r = Invoke-WebRequest $url -TimeoutSec 3; Write-Output "$url : $($r.StatusCode)" }
        catch { Write-Output "$url : unavailable" }
    }
    exit
}
if (Test-Path (Join-Path $data 'processes.json')) { throw 'Site already managed; use status or stop first.' }
New-Item $data -ItemType Directory -Force | Out-Null
Start-Process -FilePath $python -ArgumentList @('"' + $script + '"','supervise') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $data 'supervisor.log') -RedirectStandardError (Join-Path $data 'supervisor-error.log') | Out-Null
$ready = $false
for ($i=0; $i -lt 40; $i++) {
    Start-Sleep 1
    try { $r = Invoke-WebRequest 'http://127.0.0.1:5177/api/v1/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ready = $true; break } } catch {}
}
if (-not $ready) { throw "Site not ready. See $data logs; do not repeatedly start." }
Write-Output 'Litera local site ready: http://127.0.0.1:5177'
