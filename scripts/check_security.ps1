# check_security.ps1 -- security one-click gate.
# Covers: SEC-05 secrets, SEC-06 dependency audit, SEC-07 frontend escaping,
# and dynamic authorization/injection counter-examples (apitest/cases).
# Exit: 1 = FAIL, 2 = BLOCKED (prerequisite or dynamic check not executed), 0 = PASS.
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$results = @()
$failCount = 0
$blockedCount = 0

function Add-Gate {
    param([string]$Name, [string]$Status, [string]$Detail)
    $script:results += [pscustomobject]@{ Gate = $Name; Status = $Status; Detail = $Detail }
    if ($Status -eq 'FAIL') { $script:failCount++ }
    if ($Status -eq 'BLOCKED') { $script:blockedCount++ }
}

Write-Host '== SEC-05 plaintext secret scan (HEAD + tracked working tree) =='
$pattern = '(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{35}|BEGIN (RSA|OPENSSH|EC)? ?PRIVATE KEY|api_key\s*=\s*[''"][^''"]{16,})'
$headHits = git grep -I -n -E $pattern HEAD -- . 2>$null
$treeHits = git grep -I -n -E $pattern -- . 2>$null
$hits = @($headHits) + @($treeHits) | Where-Object { $_ } | Sort-Object -Unique
if ($hits) {
    $hits | ForEach-Object { Write-Host $_ }
    Add-Gate 'SEC-05 secrets' 'FAIL' "$(@($hits).Count) suspected plaintext secret line(s)"
} else {
    Add-Gate 'SEC-05 secrets' 'PASS' '0 hits in HEAD and tracked working tree'
}

Write-Host ''
Write-Host '== SEC-07 frontend output escaping (no raw HTML sinks) =='
$sinkPattern = 'v-html|innerHTML|outerHTML|document\.write'
$sinkHits = Get-ChildItem (Join-Path $root 'frontend/src') -Recurse -File -Include *.vue,*.ts,*.js -ErrorAction SilentlyContinue |
    Select-String -Pattern $sinkPattern
if ($sinkHits) {
    $sinkHits | ForEach-Object { Write-Host ("{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) }
    Add-Gate 'SEC-07 escaping' 'FAIL' "$(@($sinkHits).Count) raw HTML sink(s)"
} else {
    Add-Gate 'SEC-07 escaping' 'PASS' '0 v-html/innerHTML/outerHTML/document.write hits'
}

Write-Host ''
Write-Host '== SEC-06 dependency audit (api container, pip-audit) =='
$dockerReady = $false
try {
    docker compose version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        docker compose ps 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $dockerReady = $true }
    }
} catch { }
if (-not $dockerReady) {
    Add-Gate 'SEC-06 dependencies' 'BLOCKED' 'docker compose stack not reachable; run docker compose up -d first'
} else {
    $shCmd = "pip show pip-audit >/dev/null 2>&1; if [ `$? -ne 0 ]; then pip install --quiet pip-audit; fi; python -m pip_audit --progress-spinner off"
    $audit = docker compose exec -T api sh -c "$shCmd" 2>&1
    $auditExit = $LASTEXITCODE
    $audit | ForEach-Object { Write-Host $_ }
    $auditRan = @($audit | Where-Object { $_ -match 'known vulnerabilities|No known vulnerabilities' }).Count -gt 0
    if ($auditExit -ne 0 -and -not $auditRan) {
        Add-Gate 'SEC-06 dependencies' 'BLOCKED' "pip-audit command failed (exit $auditExit)"
    } else {
        $vulnLines = @($audit | Where-Object { $_ -match 'CVE-|PYSEC-|GHSA-' })
        $runtimeLines = @($vulnLines | Where-Object { $_ -notmatch '^\s*pip\s' })
        if ($runtimeLines.Count -gt 0) {
            Add-Gate 'SEC-06 dependencies' 'FAIL' "$($runtimeLines.Count) runtime advisory line(s); register or upgrade them"
        } elseif ($vulnLines.Count -gt 0) {
            Add-Gate 'SEC-06 dependencies' 'PASS' "$($vulnLines.Count) build-time pip advisory line(s), disposition in reports/security-baseline.md"
        } else {
            Add-Gate 'SEC-06 dependencies' 'PASS' '0 advisories'
        }
    }
}

Write-Host ''
Write-Host '== SEC-02/03/INJ dynamic counter-examples (real Compose stack) =='
$base = if ($env:APITEST_BASE) { $env:APITEST_BASE.TrimEnd('/') } else { 'http://localhost:8085/api/v1' }
$health = 0
try {
    $healthText = & curl.exe -s -o NUL -w "%{http_code}" --max-time 3 "$base/health" 2>$null
    [int]::TryParse("$healthText".Trim(), [ref]$health) | Out-Null
} catch { }
if ($health -ne 200) {
    Add-Gate 'SEC dynamic cases' 'BLOCKED' "health probe $base/health returned $health; start the stack and retry"
} else {
    $cases = @(
        'sec03-authz-write-404.ps1',
        'inj01-sqli-returns-empty.ps1',
        'inj02-xss-title-escaped-in-vue.ps1',
        'inj03-csrf-origin-and-tokens.ps1',
        'qa-injection.ps1'
    )
    foreach ($case in $cases) {
        $path = Join-Path $root "apitest/cases/$case"
        Write-Host "-- $case --"
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $path 2>&1
        $out | ForEach-Object { Write-Host "  $_" }
        # Some legacy cases exit 0 after printing a RED line; detect it explicitly.
        $printedRed = @($out | Where-Object { $_ -match '\[RED\]' }).Count -gt 0
        if ($LASTEXITCODE -eq 1 -or $printedRed) {
            Add-Gate "case $case" 'FAIL' 'assertion failed'
        } elseif ($LASTEXITCODE -eq 2 -or @($out | Where-Object { $_ -match '^CASE .* SKIP|missing both accounts|no account' }).Count -gt 0) {
            Add-Gate "case $case" 'BLOCKED' 'skipped: missing credentials or service-dependent fixture'
        } else {
            Add-Gate "case $case" 'PASS' 'assertions passed'
        }
    }
}

Write-Host ''
Write-Host '== security gate summary =='
$results | Format-Table -AutoSize | Out-String | Write-Host
if ($failCount -gt 0) { Write-Host "RESULT FAIL ($failCount failed, $blockedCount blocked)"; exit 1 }
if ($blockedCount -gt 0) { Write-Host "RESULT BLOCKED ($blockedCount not executed)"; exit 2 }
Write-Host 'RESULT PASS'
exit 0
