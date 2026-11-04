. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'x-error-envelope'
$r1 = Api-Req $null 'GET' '/documents'
Check-True 'error envelope has code' ($r1.Text -match '"error"\s*:\s*\{[^}]*"code"') ''
Check-True 'error envelope has message' ($r1.Text -match '"message"') ''
Check-True 'error envelope has requestId' ($r1.Text -match '"requestId"') ''
$r2 = Api-Req $null 'GET' '/documents'
$id1 = ([regex]::Match($r1.Text, '"requestId"\s*:\s*"([^"]+)"')).Groups[1].Value
$id2 = ([regex]::Match($r2.Text, '"requestId"\s*:\s*"([^"]+)"')).Groups[1].Value
Check-True 'requestId random per request (excluded from comparisons)' ($id1 -ne $id2 -and $id1 -ne '') "$id1 vs $id2"
Complete-Case
