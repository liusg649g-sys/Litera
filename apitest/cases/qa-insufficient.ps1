. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'qa-insufficient'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$final = Wait-DocStatus $c $id 'completed' 120
if (-not $final -or $final.parseStatus -ne 'completed') { Remove-Doc $c $id; Skip-Case 'extraction not completed' }
Start-Sleep -Seconds 20
$body = @{ mode = 'question'; question = 'What is the weather forecast for Mars tomorrow?' }
$r = Api-Req $c 'POST' "/documents/$id/qa" $body
Check 'ask 200' $r.Status 200
$j = $r.Text | ConvertFrom-Json
Check-True 'status insufficient_evidence (no hallucination)' ($j.status -eq 'insufficient_evidence') "status=$($j.status)"
Remove-Doc $c $id
Complete-Case
