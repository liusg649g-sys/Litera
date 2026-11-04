. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'auth-csrf-matrix'
$c = Require-AccountA
$pdf = Fixture-Path 'normal.pdf'
# write op without x-csrf-token
$r1 = Invoke-Curl @('-b', $c.Jar, '-H', "Origin: $script:Origin", '-F', "file=@$pdf;type=application/pdf", "$script:Base/documents")
Check 'upload without x-csrf-token -> 403' $r1.Status 403
# write op without Origin
$r2 = Invoke-Curl @('-b', $c.Jar, '-H', "x-csrf-token: $($c.Csrf)", '-F', "file=@$pdf;type=application/pdf", "$script:Base/documents")
Check 'upload without Origin -> 403' $r2.Status 403
Complete-Case
