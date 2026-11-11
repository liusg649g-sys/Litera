# INJ-03 CSRF cross-site: forged write requests from wrong Origin get INVALID_ORIGIN
# Two switches: (a) missing Origin -> reject; (b) evil Origin -> reject
. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$cfg = Get-Config
if (-not $cfg.EmailA) { Write-Host 'no account'; exit 2 }
$c = New-Client $cfg.EmailA $cfg.PassA
$csrf = $c.Csrf

$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$payload = Write-JsonTmp @{ title = 'x'; version = 1 }

# (a) PATCH without Origin header
$a = Invoke-Curl @('-X', 'PATCH', '-b', $c.Jar, '-H', "x-csrf-token: $csrf",
    '-H', 'Content-Type: application/json', '--data-binary', "@$payload",
    "$script:Base/documents/$id")
Remove-Item $payload -Force -ErrorAction SilentlyContinue
Check 'no Origin -> 403' $a.Status 403
$code = ''; try { $code = (($a.Text | ConvertFrom-Json).error.code) } catch { }
Check-True 'error code is INVALID_ORIGIN/CSRF' ($code -eq 'INVALID_ORIGIN' -or $code -eq 'INVALID_CSRF_TOKEN') "code=$code"

# (b) Origin from evil.com
$b = Invoke-Curl @('-X', 'PATCH', '-b', $c.Jar,
    '-H', 'Origin: http://evil.com', '-H', "x-csrf-token: $csrf",
    '-H', 'Content-Type: application/json', '--data-binary',
    ($(ConvertTo-Json @{ title = 'x'; version = 1 })),
    "$script:Base/documents/$id")
Check-True 'evil Origin rejected (not 200)' ($b.Status -ne 200) "status=$($b.Status)"

# cleanup
Api-Req $c 'DELETE' "/documents/$id" | Out-Null
Api-Req $c 'DELETE' "/trash/documents/$id" | Out-Null
Write-Host "INJ03 (a) no Origin -> $($a.Status) code=$code (b) evil Origin -> $($b.Status)"
exit 0
