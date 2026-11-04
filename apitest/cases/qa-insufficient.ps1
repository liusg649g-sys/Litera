. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'qa-insufficient'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$final = Wait-DocStatus $c $id 'completed' 120
if (-not $final -or $final.parseStatus -ne 'completed') { Remove-Doc $c $id; Skip-Case 'extraction not completed' }
$r = Ask-Qa $c $id 'What is the weather forecast for Mars tomorrow?' 180
Check 'ask 200 (after index build retries)' $r.Status 200
if ($r.Status -eq 200) {
    $j = $r.Text | ConvertFrom-Json
    Check-True 'status insufficient_evidence (no hallucination)' ($j.status -eq 'insufficient_evidence') "status=$($j.status)"
    Check-True 'no citations attached to refusal' ($r.Text -match '"citations"\s*:\s*\[\s*\]') ''
}
Remove-Doc $c $id
Complete-Case
