. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-patch-metadata'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$newTitle = "Apitest Title $([guid]::NewGuid().ToString('N').Substring(0,6))"
$p = Api-Req $c 'PATCH' "/documents/$id" @{ title = $newTitle }
Check 'PATCH 200' $p.Status 200
$g = Api-Req $c 'GET' "/documents/$id"
Check-True 'title persisted' (($g.Text | ConvertFrom-Json).title -eq $newTitle) $newTitle
$bad = Api-Req $c 'PATCH' "/documents/$id" @{ title = '' }
Check-Match 'empty title -> 4xx' "$($bad.Status)" '^4\d\d$'
Remove-Doc $c $id
Complete-Case
