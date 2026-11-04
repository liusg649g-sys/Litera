. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'trans-selection'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$body = @{ text = 'The zebra-telegraph method is a deterministic test technique.'; sourceLanguage = 'en'; targetLanguage = 'zh'; pageNumber = 1 }
$r = Api-Req $c 'POST' "/documents/$id/translations" $body
Check 'translate 200' $r.Status 200
Check-True 'result contains Chinese' ($r.Text -match '[一-鿿]') ($r.Text.Substring(0, [Math]::Min(80, $r.Text.Length)))
Remove-Doc $c $id
Complete-Case
