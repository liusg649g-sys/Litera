. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-trash-lifecycle'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$d1 = Api-Req $c 'DELETE' "/documents/$id"
Check-Match 'soft delete 2xx' "$($d1.Status)" '^2\d\d$'
$g1 = Api-Req $c 'GET' "/documents/$id"
Check 'gone from library -> 404' $g1.Status 404
$trash = Api-Req $c 'GET' '/trash/documents'
Check-True 'visible in trash' ($trash.Text -match $id) ''
$rs = Api-Req $c 'POST' "/trash/documents/$id/restore"
Check-Match 'restore 2xx' "$($rs.Status)" '^2\d\d$'
$g2 = Api-Req $c 'GET' "/documents/$id"
Check 'restored -> 200' $g2.Status 200
Api-Req $c 'DELETE' "/documents/$id" | Out-Null
$d2 = Api-Req $c 'DELETE' "/trash/documents/$id"
Check-Match 'purge 2xx' "$($d2.Status)" '^2\d\d$'
$g3 = Api-Req $c 'GET' "/documents/$id"
Check 'purged -> 404' $g3.Status 404
Complete-Case
