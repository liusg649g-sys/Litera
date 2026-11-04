. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-authz-matrix'
$cfg = Get-Config
if (-not $cfg.EmailB -or -not $cfg.PassB) { Skip-Case 'needs account B: set APITEST_EMAIL_B/APITEST_PASSWORD_B' }
$a = New-Client $cfg.EmailA $cfg.PassA
$b = New-Client $cfg.EmailB $cfg.PassB
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $a $pdf
$id = ($up.Text | ConvertFrom-Json).id
$r1 = Api-Req $b 'GET' "/documents/$id"
Check 'B reads A doc -> 404' $r1.Status 404
$r2 = Api-Req $b 'GET' '/documents/00000000-0000-0000-0000-000000000000'
Check 'B reads missing id -> 404' $r2.Status 404
Check-True '404 body identical semantics' (($r1.Text -replace '"requestId":"[^"]+"','') -eq ($r2.Text -replace '"requestId":"[^"]+"','')) 'requestId excluded'
$gA = Api-Req $a 'GET' "/documents/$id"
$v = ($gA.Text | ConvertFrom-Json).version
$r3 = Api-Req $b 'PATCH' "/documents/$id" @{ version = $v; title = 'hijacked' }
Check 'B patches A doc -> 404' $r3.Status 404
$g = Api-Req $a 'GET' "/documents/$id"
Check-True 'A title unchanged' (($g.Text | ConvertFrom-Json).title -ne 'hijacked') ''
Remove-Doc $a $id
Complete-Case
