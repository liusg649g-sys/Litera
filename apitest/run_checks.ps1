# apitest/run_checks.ps1 -- run all cases, aggregate verdicts, write reports/ log.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File apitest/run_checks.ps1 [-Filter docs-*]
param([string]$Filter = '*')
if ([string]::IsNullOrWhiteSpace($Filter)) { $Filter = '*' }
$here = $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $here 'reports'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "check-$stamp.log"
$green = 0; $red = 0; $skip = 0
$cases = Get-ChildItem (Join-Path $here 'cases') -Filter "$Filter.ps1" | Sort-Object Name
if (-not $cases) { Write-Host "no cases matched '$Filter'"; exit 2 }
foreach ($case in $cases) {
    Write-Host "== $($case.BaseName) =="
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $case.FullName 2>&1
    $out | ForEach-Object { Write-Host "  $_" }
    $out | Out-File -Append -Encoding utf8 $log
    switch ($LASTEXITCODE) { 0 { $green++ } 2 { $skip++ } default { $red++ } }
}
$summary = "GREEN $green / RED $red / SKIP $skip"
Write-Host "== $summary =="
"CASES $($cases.Count)" | Out-File -Append -Encoding utf8 $log
$summary | Out-File -Append -Encoding utf8 $log
Write-Host "log: $log"
if ($red -gt 0) { exit 1 } else { exit 0 }
