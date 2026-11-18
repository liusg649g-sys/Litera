# check_all.ps1 -- non-security one-click gate for six categories.
#   API-ENTRY / BUSINESS-LOGIC / DATABASE / COMMON-FUNCTIONS / ERROR-HANDLING / PERFORMANCE
# Security negatives live in scripts/check_security.ps1 (make check-security).
# Exit: 1 = FAIL, 2 = BLOCKED (prerequisite or dynamic check not executed), 0 = PASS.
param(
    [string]$Filter = '*',
    [string]$CoverageMin = '80'
)
$ErrorActionPreference = 'Continue'
if ([string]::IsNullOrWhiteSpace($Filter)) { $Filter = '*' }
if ([string]::IsNullOrWhiteSpace($CoverageMin)) { $CoverageMin = '80' }
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'backend'
$reportDir = Join-Path $root 'reports'
New-Item -ItemType Directory -Force $reportDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $reportDir "check-all-$stamp.log"
$results = @()
$failCount = 0
$blockedCount = 0

function Add-Gate {
    param([string]$Category, [string]$Status, [string]$Detail)
    $script:results += [pscustomobject]@{ Category = $Category; Status = $Status; Detail = $Detail }
    if ($Status -eq 'FAIL') { $script:failCount++ }
    if ($Status -eq 'BLOCKED') { $script:blockedCount++ }
}

function Resolve-Python {
    if ($env:LITERA_PYTHON -and (Test-Path $env:LITERA_PYTHON)) { return $env:LITERA_PYTHON }
    $venv = Join-Path $backend '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Invoke-Pytest {
    param([string[]]$PytestArgs)
    Push-Location $backend
    try {
        $out = & $python -m pytest @PytestArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $out | ForEach-Object { Write-Host $_ }
    $out | Out-File -Append -Encoding utf8 $log
    return $code
}

function Category-FromCases {
    param([array]$Records, [string[]]$Patterns)
    $matched = @($Records | Where-Object {
        $name = $_.case
        @($Patterns | Where-Object { $name -like $_ }).Count -gt 0
    })
    $fails = @($matched | Where-Object { $_.status -eq 'FAIL' }).Count
    $passes = @($matched | Where-Object { $_.status -eq 'PASS' }).Count
    $skips = @($matched | Where-Object { $_.status -eq 'SKIP' }).Count
    if ($fails -gt 0) { return @('FAIL', "$fails failed / $passes passed / $skips skipped") }
    if ($passes -gt 0) { return @('PASS', "$passes passed / $skips skipped") }
    if ($matched.Count -eq 0) { return @('BLOCKED', 'no matching apitest cases') }
    return @('BLOCKED', "0 executed / $skips skipped")
}

$python = Resolve-Python
$pythonReady = $false
if ($python) {
    & $python -c "import fastapi, pytest, pytest_cov" 2>$null
    $pythonReady = ($LASTEXITCODE -eq 0)
}
if (-not $pythonReady) {
    Write-Host 'Python with fastapi/pytest/pytest-cov not found.'
    Write-Host 'Create backend/.venv and install: pip install -r backend/requirements-dev.txt'
    foreach ($category in 'COMMON-FUNCTIONS', 'DATABASE', 'BUSINESS-LOGIC', 'ERROR-HANDLING', 'PERFORMANCE') {
        Add-Gate $category 'BLOCKED' 'python test environment not ready'
    }
    Add-Gate 'API-ENTRY' 'BLOCKED' 'python test environment not ready (see README)'
} else {
    $env:TEST_DATABASE_URL = ''
    $env:APP_ENV = 'test'

    Write-Host ''
    Write-Host '== COMMON-FUNCTIONS: backend unit tests + coverage gate =='
    # Service-dependent async extraction tests are covered by apitest extr-*;
    # migration/query/audit files run in their own category gates below.
    $unitArgs = @(
        'tests', '-q', '--tb=short',
        '--ignore=tests/test_metadata_extraction_async.py',
        '--ignore=tests/test_migrations_gate.py',
        '--ignore=tests/test_notes_migration.py',
        '--ignore=tests/test_user_models_migration.py',
        '--ignore=tests/test_delivery_compatibility.py',
        '--ignore=tests/test_query_performance.py',
        '--ignore=tests/test_audit_outcomes.py',
        '--cov=app', '--cov-report=term', "--cov-fail-under=$CoverageMin",
        "--junitxml=$(Join-Path $reportDir 'pytest-unit.xml')"
    )
    $code = Invoke-Pytest $unitArgs
    if ($code -eq 0) { Add-Gate 'COMMON-FUNCTIONS' 'PASS' "unit tests green, coverage >= $CoverageMin%" }
    else { Add-Gate 'COMMON-FUNCTIONS' 'FAIL' "pytest exit $code (tests or coverage below $CoverageMin%)" }

    Write-Host ''
    Write-Host '== DATABASE: migration chain / repeat head / indexes / rollback =='
    $dbArgs = @(
        'tests/test_migrations_gate.py', 'tests/test_notes_migration.py',
        'tests/test_user_models_migration.py', 'tests/test_delivery_compatibility.py',
        '-q', '--tb=short'
    )
    $code = Invoke-Pytest $dbArgs
    if ($code -eq 0) { Add-Gate 'DATABASE' 'PASS' 'migration chain, repeat head, indexes and rollback refusal passed' }
    else { Add-Gate 'DATABASE' 'FAIL' "pytest exit $code" }

    Write-Host ''
    Write-Host '== BUSINESS-LOGIC: scenario traceability (semantic review stays manual) =='
    Push-Location $root
    try { $out = & $python scripts/check_scenarios.py 2>&1; $code = $LASTEXITCODE } finally { Pop-Location }
    $out | ForEach-Object { Write-Host $_ }
    $out | Out-File -Append -Encoding utf8 $log
    $businessStaticOk = ($code -eq 0)

    Write-Host ''
    Write-Host '== ERROR-HANDLING: audit outcomes (success / failed / denied) =='
    $auditArgs = @('tests/test_audit_outcomes.py', '-q', '--tb=short')
    $code = Invoke-Pytest $auditArgs
    $errorStaticOk = ($code -eq 0)

    Write-Host ''
    Write-Host '== PERFORMANCE: isolated N+1 / slow-statement gate =='
    $perfArgs = @('tests/test_query_performance.py', '-q', '--tb=short')
    $code = Invoke-Pytest $perfArgs
    $isolatedPerf = ($code -eq 0)
    if ($isolatedPerf) { Write-Host 'isolated query gate: PASS (see reports/query-performance.json)' }

    Write-Host ''
    Write-Host '== API-ENTRY / BUSINESS-LOGIC / ERROR-HANDLING / PERFORMANCE: real Compose apitest =='
    $base = if ($env:APITEST_BASE) { $env:APITEST_BASE.TrimEnd('/') } else { 'http://localhost:8085/api/v1' }
    $health = 0
    try {
        $healthText = & curl.exe -s -o NUL -w "%{http_code}" --max-time 3 "$base/health" 2>$null
        [int]::TryParse("$healthText".Trim(), [ref]$health) | Out-Null
    } catch { }
    $records = @()
    if ($health -ne 200) {
        Write-Host "service health $base/health -> $health; dynamic cases not executed"
    } else {
        $json = Join-Path $reportDir "apitest-$stamp.json"
        $runner = Join-Path $root 'apitest/run_checks.ps1'
        $apiOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $runner -Filter $Filter -ExcludeSecurity -JsonOut $json 2>&1
        $apiOut | ForEach-Object { Write-Host $_ }
        $apiOut | Out-File -Append -Encoding utf8 $log
        if (Test-Path $json) {
            $parsed = Get-Content $json -Raw | ConvertFrom-Json
            $records = @($parsed)
        }
    }

    $entry = Category-FromCases -Records $records -Patterns @('auth-*', 'docs-*', 'anno-*', 'x-*')
    Add-Gate 'API-ENTRY' $entry[0] $entry[1]

    $business = Category-FromCases -Records $records -Patterns @('docs-*', 'anno-*', 'extr-*', 'trans-*', 'notes-*', 'qa-*')
    if (-not $businessStaticOk) { Add-Gate 'BUSINESS-LOGIC' 'FAIL' 'scenario traceability failed' }
    elseif ($business[0] -eq 'FAIL') { Add-Gate 'BUSINESS-LOGIC' 'FAIL' $business[1] }
    elseif ($business[0] -eq 'PASS' -and $health -eq 200) { Add-Gate 'BUSINESS-LOGIC' 'PASS' "traceability + scenario cases: $($business[1])" }
    else { Add-Gate 'BUSINESS-LOGIC' 'BLOCKED' "traceability passed; scenario cases $($business[0]): $($business[1])" }

    $errors = Category-FromCases -Records $records -Patterns @('x-error-envelope', 'extr-manual-retry', 'extr-stop-start')
    if (-not $errorStaticOk) { Add-Gate 'ERROR-HANDLING' 'FAIL' 'audit outcome test failed' }
    elseif ($errors[0] -eq 'FAIL') { Add-Gate 'ERROR-HANDLING' 'FAIL' $errors[1] }
    elseif ($errors[0] -eq 'PASS' -and $health -eq 200) { Add-Gate 'ERROR-HANDLING' 'PASS' "audit + fault-injection: $($errors[1])" }
    else { Add-Gate 'ERROR-HANDLING' 'BLOCKED' "audit passed; fault-injection $($errors[0]): $($errors[1])" }

    $load = Category-FromCases -Records $records -Patterns @('extr-p95-concurrency')
    if (-not $isolatedPerf) { Add-Gate 'PERFORMANCE' 'FAIL' 'isolated query performance gate failed' }
    elseif ($load[0] -eq 'PASS') { Add-Gate 'PERFORMANCE' 'PASS' "query gate + P95 load case passed" }
    else { Add-Gate 'PERFORMANCE' 'BLOCKED' "query gate passed; load case $($load[0]): $($load[1])" }
}

Write-Host ''
Write-Host '== check-all summary =='
$results | Format-Table -AutoSize | Out-String | Write-Host
$results | Format-Table -AutoSize | Out-File -Append -Encoding utf8 $log
Write-Host "log: $log"
if ($failCount -gt 0) { Write-Host "RESULT FAIL ($failCount failed, $blockedCount blocked)"; exit 1 }
if ($blockedCount -gt 0) { Write-Host "RESULT BLOCKED ($blockedCount not executed)"; exit 2 }
Write-Host 'RESULT PASS'
exit 0
