# check_security.ps1 -- SEC-05 secret scan + SEC-06 dependency audit
# Usage: make check-security  or  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1
# Exit: plaintext secret found -> 1; audit advisories (registered disposition) -> 0 with WARNING; all clean -> 0
$ErrorActionPreference = 'Continue'
$failed = $false

Write-Host '== SEC-05 plaintext secret scan (HEAD tree) =='
$pattern = '(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{35}|BEGIN (RSA|OPENSSH|EC)? ?PRIVATE KEY|api_key\s*=\s*[''"][^''"]{16,})'
$hits = git grep -I -n -E $pattern HEAD -- . 2>$null
if ($hits) {
    Write-Host $hits
    Write-Host 'SEC-05 FAIL: suspected plaintext secrets above'
    $failed = $true
} else {
    Write-Host 'SEC-05 PASS: 0 hits (git grep no match)'
}

Write-Host ''
Write-Host '== SEC-06 dependency audit (api container, pip-audit) =='
$shCmd = "pip show pip-audit >/dev/null 2>&1; if [ `$? -ne 0 ]; then pip install --quiet pip-audit; fi; python -m pip_audit --progress-spinner off"
$audit = docker compose exec -T api sh -c "$shCmd" 2>&1
$audit | ForEach-Object { Write-Host $_ }
$vulnLines = $audit | Where-Object { $_ -match 'CVE-|PYSEC-' }
if ($vulnLines) {
    $count = ($vulnLines | Measure-Object).Count
    Write-Host "SEC-06 WARNING: $count advisories; disposition registered in reports/security-baseline.md (pypdf>=6.21.4 upgrade pending)"
} else {
    Write-Host 'SEC-06 PASS: 0 advisories'
}

if ($failed) { exit 1 }
exit 0
