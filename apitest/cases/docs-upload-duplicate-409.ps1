. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-upload-duplicate-409'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$r1 = Upload-Pdf $c $pdf
Check 'first upload 201' $r1.Status 201
$id = ($r1.Text | ConvertFrom-Json).id
$r2 = Upload-Pdf $c $pdf
Check 'second identical upload 409' $r2.Status 409
Check-True 'error code DUPLICATE_DOCUMENT' ($r2.Text -match 'DUPLICATE_DOCUMENT') ''
Remove-Doc $c $id
Complete-Case
