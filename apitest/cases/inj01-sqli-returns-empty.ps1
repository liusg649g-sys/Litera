# INJ-01 SQL injection: q=' OR '1'='1 returns empty, not all rows
. "$PSScriptRoot\..\lib\common.ps1"
$cfg = Get-Config
if (-not $cfg.EmailA) { Write-Host 'no account'; exit 2 }
$c = New-Client $cfg.EmailA $cfg.PassA

# malicious search string -- in SQL concat world this returns every row
$r = Api-Req $c 'GET' '/documents?q=%27%20OR%20%271%27%3D%271'
Check 'list 200 (not 500/404)' $r.Status 200
$j = $r.Text | ConvertFrom-Json
# must NOT return every document the user owns (which would mean injection succeeded)
$totalOwned = (Api-Req $c 'GET' '/documents').Text | ConvertFrom-Json | Select-Object -ExpandProperty total
Check-True 'injection does not return all rows' ($j.total -lt $totalOwned -or $j.total -eq 0) "injection_total=$($j.total) owned_total=$totalOwned"
Write-Host "INJ01 injection total=$($j.total) owned=$totalOwned"
exit 0
