# SEC-03 A session PATCH B document -> expect 404, title unchanged
. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$cfg = Get-Config
if (-not $cfg.EmailA -or -not $cfg.EmailB) { Write-Host 'missing both accounts'; exit 2 }

$a = New-Client $cfg.EmailA $cfg.PassA
$b = New-Client $cfg.EmailB $cfg.PassB

$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$upB = Upload-Pdf $b $pdf
$bid = ($upB.Text | ConvertFrom-Json).id
Write-Host "SEC03 B upload id=$bid"

# A (other user) PATCH B's document -> 404
$r = Api-Req $a 'PATCH' "/documents/$bid" @{ title = 'ATTACKED BY A'; version = 1 }
Check 'A PATCH B -> 404' $r.Status 404

# B reads back, title unchanged
$r2 = Api-Req $b 'GET' "/documents/$bid"
Check 'B GET still 200' $r2.Status 200
$j = $r2.Text | ConvertFrom-Json
Check-True 'title unchanged' ($j.title -ne 'ATTACKED BY A') "got=$($j.title)"

# cleanup
Api-Req $b 'DELETE' "/documents/$bid" | Out-Null
Api-Req $b 'DELETE' "/trash/documents/$bid" | Out-Null
Write-Host 'SEC03 cleanup done'
exit 0
