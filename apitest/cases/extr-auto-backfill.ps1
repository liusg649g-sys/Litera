. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-auto-backfill'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
Check 'upload 201' $up.Status 201
$doc = $up.Text | ConvertFrom-Json
Check 'upload response parseStatus=processing (frontend polling contract)' $doc.parseStatus 'processing'
$final = Wait-DocStatus $c $doc.id 'completed' 120
Check-True 'reaches completed within 120s' ($null -ne $final -and $final.parseStatus -eq 'completed') "actual=$($final.parseStatus)"
Check-True 'extractionVersion present' ($null -ne $final.extractionVersion -and $final.extractionVersion -ne '') $final.extractionVersion
Check-True 'metadata auto-backfilled (doi)' ($final.doi -eq '10.5555/apitest.2026.001') "doi=$($final.doi)"
Remove-Doc $c $doc.id
Complete-Case
