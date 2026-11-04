. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'anno-crud'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$docId = ($up.Text | ConvertFrom-Json).id
# Collection revision starts at 0; every write is a command carrying commandId + baseRevision.
$g0 = Api-Req $c 'GET' "/documents/$docId/annotations"
Check 'list annotations 200' $g0.Status 200
$rev = ($g0.Text | ConvertFrom-Json).annotationRevision
Check-True 'fresh collection revision is 0' ($rev -eq 0) "annotationRevision=$rev"
$annoId = [guid]::NewGuid().ToString()
$cmd = [guid]::NewGuid().ToString()
# highlight requires a real text anchor: position must equal geometry.positions and selectedText present
$pos = @(@{ pageNumber = 1; rects = @(@{ x = 0.1; y = 0.1; width = 0.3; height = 0.05 }); textQuote = 'zebra-telegraph' })
$payload = @{
    commandId = $cmd; baseRevision = 0
    annotation = @{
        id = $annoId; type = 'highlight'; schemaVersion = 1; pageNumber = 1
        position = $pos
        geometry = @{ kind = 'text'; positions = $pos }
        selectedText = 'zebra-telegraph'; color = '#FFDD00'
    }
}
$p = Api-Req $c 'POST' "/documents/$docId/annotations" $payload
Check 'create annotation 201' $p.Status 201
if ($p.Status -ne 201) { Write-Host "  payload-hint: $($p.Text)" }
$j = $p.Text | ConvertFrom-Json
Check-True 'command receipt echoes commandId' ($j.commandId -eq $cmd) ''
Check-True 'revision advanced to 1' ($j.annotationRevision -eq 1) "annotationRevision=$($j.annotationRevision)"
$same = Api-Req $c 'POST' "/documents/$docId/annotations" $payload
# Replay hits the stored command receipt: no new row. Route-level status_code=201 applies to both calls.
Check-Match 'same commandId replay -> 2xx (receipt hit, no duplicate)' "$($same.Status)" '^2\d\d$'
Check-True 'replay returns identical receipt payload' (($same.Text | ConvertFrom-Json).commandId -eq $cmd -and ($same.Text | ConvertFrom-Json).annotationRevision -eq 1) ''
$g = Api-Req $c 'GET' "/documents/$docId/annotations"
Check-True 'exactly one annotation after replay' ((($g.Text | ConvertFrom-Json).items).Count -eq 1) ''
Check-True 'rect readback width=0.3' ($g.Text -match '"width":\s*0\.3') ''
$v = ($g.Text | ConvertFrom-Json).items[0].version
$del = Api-Req $c 'DELETE' "/documents/$docId/annotations/$annoId" @{ commandId = [guid]::NewGuid().ToString(); baseRevision = 1; version = $v }
Check 'delete annotation 2xx' ([int]($del.Status / 100)) 2
$g2 = Api-Req $c 'GET' "/documents/$docId/annotations"
Check-True 'annotation gone' ($g2.Text -notmatch $annoId) ''
Remove-Doc $c $docId
Complete-Case
