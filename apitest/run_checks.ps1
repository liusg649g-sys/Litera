# apitest/run_checks.ps1 -- run all cases, aggregate verdicts, write report + JSON.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File apitest/run_checks.ps1 [-Filter docs-*] [-Exclude sec-*,inj-*]
param(
    [string]$Filter = '*',
    [string[]]$Exclude = @(),
    [switch]$ExcludeSecurity,
    [string]$JsonOut = ''
)
if ([string]::IsNullOrWhiteSpace($Filter)) { $Filter = '*' }
if ($ExcludeSecurity) { $Exclude += @('sec*.ps1', 'inj*.ps1', 'qa-injection.ps1') }
$here = $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $here 'reports'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "check-$stamp.log"
if ([string]::IsNullOrWhiteSpace($JsonOut)) { $JsonOut = Join-Path $logDir 'last-run.json' }
$green = 0; $red = 0; $skip = 0
$records = @()
$cases = Get-ChildItem (Join-Path $here 'cases') -Filter "$Filter.ps1" | Sort-Object Name
if ($Exclude.Count -gt 0) {
    $cases = $cases | Where-Object {
        $name = $_.Name
        -not ($Exclude | Where-Object { $name -like $_ })
    }
}
if (-not $cases) { Write-Host "no cases matched '$Filter'"; exit 2 }
foreach ($case in $cases) {
    Write-Host "== $($case.BaseName) =="
    $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $case.FullName 2>&1
    $out | ForEach-Object { Write-Host "  $_" }
    $out | Out-File -Append -Encoding utf8 $log
    $status = switch ($LASTEXITCODE) { 0 { 'PASS' } 2 { 'SKIP' } default { 'FAIL' } }
    switch ($status) { 'PASS' { $green++ } 'SKIP' { $skip++ } default { $red++ } }
    $records += [pscustomobject]@{ case = $case.BaseName; status = $status; exitCode = $LASTEXITCODE }
}
$summary = "GREEN $green / RED $red / SKIP $skip"
Write-Host "== $summary =="
"CASES $($cases.Count)" | Out-File -Append -Encoding utf8 $log
$summary | Out-File -Append -Encoding utf8 $log
$records | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 $JsonOut
Write-Host "log: $log"
Write-Host "json: $JsonOut"
if ($red -gt 0) { exit 1 } else { exit 0 }
