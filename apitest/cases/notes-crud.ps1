. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'notes-crud'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$docId = ($up.Text | ConvertFrom-Json).id
$noteId = [guid]::NewGuid().ToString()
$title = "apitest-note-$([guid]::NewGuid().ToString('N').Substring(0,6))"
$p = Api-Req $c 'POST' '/notes' @{ id = $noteId; title = $title; content = 'first draft'; documentId = $docId }
Check 'create note 201' $p.Status 201
$g = Api-Req $c 'GET' "/notes/$noteId"
Check 'read note 200' $g.Status 200
Check-True 'title persisted' (($g.Text | ConvertFrom-Json).title -eq $title) $title
$v1 = ($g.Text | ConvertFrom-Json).version
$u = Api-Req $c 'PATCH' "/notes/$noteId" @{ version = $v1; content = 'autosaved v2' }
Check-Match 'autosave PATCH 2xx' "$($u.Status)" '^2\d\d$'
$g2 = Api-Req $c 'GET' "/notes/$noteId"
Check-True 'content updated' ($g2.Text -match 'autosaved v2') ''
Check-True 'version incremented' ((($g2.Text | ConvertFrom-Json).version) -gt $v1) "was $v1"
$v2 = ($g2.Text | ConvertFrom-Json).version
$stale = Api-Req $c 'PATCH' "/notes/$noteId" @{ version = $v1; content = 'stale' }
Check 'stale version -> 409' $stale.Status 409
$d = Api-Req $c 'DELETE' "/notes/$noteId`?version=$v2"
Check 'delete 204' $d.Status 204
$g3 = Api-Req $c 'GET' "/notes/$noteId"
Check 'deleted -> 404' $g3.Status 404
Remove-Doc $c $docId
Complete-Case
