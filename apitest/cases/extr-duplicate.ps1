. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-duplicate'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$r1 = Upload-Pdf $c $pdf
Check 'first submit 201' $r1.Status 201
$id = ($r1.Text | ConvertFrom-Json).id
$r2 = Upload-Pdf $c $pdf
Check 'duplicate submit 409 (no second job created)' $r2.Status 409
Wait-DocStatus $c $id 'completed' 120 | Out-Null
$cand = Api-Req $c 'GET' "/documents/$id/extraction-candidates"
$j = $cand.Text | ConvertFrom-Json
Check-True 'single extraction version in effect' ($null -ne $j.extractionVersion) $j.extractionVersion
$list = Api-Req $c 'GET' '/documents'
$fn = ($r1.Text | ConvertFrom-Json).fileName
$count = ([regex]::Matches($list.Text, [regex]::Escape("`"id`"")))  # count docs, sanity only
Check-True 'library readable after duplicate attempt' ($list.Status -eq 200) ''
Remove-Doc $c $id
Complete-Case
