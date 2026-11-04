. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'qa-answer-citations'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$final = Wait-DocStatus $c $id 'completed' 120
if (-not $final -or $final.parseStatus -ne 'completed') { Remove-Doc $c $id; Skip-Case 'extraction not completed; QA needs chunks' }
Start-Sleep -Seconds 20  # allow embedding index sweep to pick up chunks
$body = @{ mode = 'question'; question = 'What is the zebra-telegraph method?' }
$r = Api-Req $c 'POST' "/documents/$id/qa" $body
Check 'ask 200' $r.Status 200
$j = $r.Text | ConvertFrom-Json
Check-True 'answer non-empty' ($j.answer -and $j.answer.Length -gt 10) ''
Check-True 'citations present with pageNumber' ($r.Text -match '"citations"' -and $r.Text -match '"pageNumber"') ''
Check-True 'answer mentions zebra-telegraph' ($j.answer -match 'zebra') ''
Remove-Doc $c $id
Complete-Case
