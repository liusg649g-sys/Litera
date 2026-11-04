. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'notes-source-search'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$docId = ($up.Text | ConvertFrom-Json).id
$noteId = [guid]::NewGuid().ToString()
$marker = "quokka-$([guid]::NewGuid().ToString('N').Substring(0,6))"
Api-Req $c 'POST' '/notes' @{ id = $noteId; title = "marker $marker"; content = "body mentions $marker"; documentId = $docId } | Out-Null
$s = Api-Req $c 'GET' "/notes/search?q=$marker"
Check 'search 200' $s.Status 200
Check-True 'search hits note' ($s.Text -match $noteId) ''
$l = Api-Req $c 'PUT' "/notes/$noteId/documents/$docId"
Check-Match 'M:N link 2xx' "$($l.Status)" '^2\d\d$'
Api-Req $c 'DELETE' "/notes/$noteId" | Out-Null
Remove-Doc $c $docId
Complete-Case
