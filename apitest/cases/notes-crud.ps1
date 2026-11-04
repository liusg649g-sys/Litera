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
$u = Api-Req $c 'PATCH' "/notes/$noteId" @{ content = 'autosaved v2' }
Check-Match 'autosave PATCH 2xx' "$($u.Status)" '^2\d\d$'
$g2 = Api-Req $c 'GET' "/notes/$noteId"
Check-True 'content updated' ($g2.Text -match 'autosaved v2') ''
$d = Api-Req $c 'DELETE' "/notes/$noteId"
Check-Match 'delete 2xx' "$($d.Status)" '^2\d\d$'
$g3 = Api-Req $c 'GET' "/notes/$noteId"
Check 'deleted -> 404' $g3.Status 404
Remove-Doc $c $docId
Complete-Case
