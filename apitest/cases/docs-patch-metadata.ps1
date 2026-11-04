. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-patch-metadata'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$g0 = Api-Req $c 'GET' "/documents/$id"
$v = ($g0.Text | ConvertFrom-Json).version
Check-True 'detail carries version for optimistic locking' ($v -ge 1) "version=$v"
$newTitle = "Apitest Title $([guid]::NewGuid().ToString('N').Substring(0,6))"
$p = Api-Req $c 'PATCH' "/documents/$id" @{ version = $v; title = $newTitle }
Check 'PATCH 200' $p.Status 200
$g = Api-Req $c 'GET' "/documents/$id"
Check-True 'title persisted' (($g.Text | ConvertFrom-Json).title -eq $newTitle) $newTitle
Check-True 'version incremented' ((($g.Text | ConvertFrom-Json).version) -eq ($v + 1)) "version=$v+1"
$stale = Api-Req $c 'PATCH' "/documents/$id" @{ version = $v; title = 'stale write' }
Check 'stale version -> 409' $stale.Status 409
$bad = Api-Req $c 'PATCH' "/documents/$id" @{ version = ($v + 1); title = '' }
Check-Match 'empty title -> 4xx' "$($bad.Status)" '^4\d\d$'
Remove-Doc $c $id
Complete-Case
