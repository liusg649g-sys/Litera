. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-endpoints-shape'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$final = Wait-DocStatus $c $id 'completed' 120
if (-not $final) { Remove-Doc $c $id; Skip-Case 'extraction did not complete in time' }
$cand = Api-Req $c 'GET' "/documents/$id/extraction-candidates"
Check 'candidates 200' $cand.Status 200
Check-True 'candidates has jobStatus' ($cand.Text -match '"jobStatus"') ''
$pages = Api-Req $c 'GET' "/documents/$id/extraction-pages"
Check 'pages 200' $pages.Status 200
Check-True 'pages contain pageNumber' ($pages.Text -match '"pageNumber":\s*1') ''
$chunks = Api-Req $c 'GET' "/documents/$id/extraction-chunks"
Check 'chunks 200' $chunks.Status 200
Check-True 'chunks carry offsets' ($chunks.Text -match 'Offset"?:\s*\d') ''
Remove-Doc $c $id
Complete-Case
