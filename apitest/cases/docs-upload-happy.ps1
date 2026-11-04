. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-upload-happy'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
Check 'upload 201' $up.Status 201
$doc = $up.Text | ConvertFrom-Json
Check-True 'response has id' ($null -ne $doc.id) "id=$($doc.id)"
$list = Api-Req $c 'GET' '/documents'
Check 'list 200' $list.Status 200
Check-True 'list contains new doc' ($list.Text -match $doc.id) ''
$one = Api-Req $c 'GET' "/documents/$($doc.id)"
Check 'detail 200' $one.Status 200
Check-True 'detail fileName matches' ($one.Text -match [regex]::Escape($doc.fileName)) $doc.fileName
Remove-Doc $c $doc.id
Complete-Case
