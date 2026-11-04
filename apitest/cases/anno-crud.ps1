. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'anno-crud'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$docId = ($up.Text | ConvertFrom-Json).id
$annoId = [guid]::NewGuid().ToString()
$payload = @{
    id = $annoId; type = 'highlight'; schemaVersion = 1; pageNumber = 1
    position = @(@{ pageNumber = 1; rects = @(@{ x = 0.1; y = 0.1; width = 0.3; height = 0.05 }); textQuote = 'zebra-telegraph' })
    geometry = @{ kind = 'box'; pageNumber = 1; rect = @{ x = 0.1; y = 0.1; width = 0.3; height = 0.05 } }
    color = '#FFDD00'; opacity = 0.5
}
$p = Api-Req $c 'POST' "/documents/$docId/annotations" $payload
Check 'create annotation 201' $p.Status 201
if ($p.Status -ne 201) { Write-Host "  payload-hint: $($p.Text)" }
$g = Api-Req $c 'GET' "/documents/$docId/annotations"
Check 'list annotations 200' $g.Status 200
Check-True 'rect readback width=0.3' ($g.Text -match '"width":\s*0\.3') ''
$d = Api-Req $c 'DELETE' "/documents/$docId/annotations/$annoId"
Check-Match 'delete annotation 2xx' "$($d.Status)" '^2\d\d$'
$g2 = Api-Req $c 'GET' "/documents/$docId/annotations"
Check-True 'annotation gone' ($g2.Text -notmatch $annoId) ''
Remove-Doc $c $docId
Complete-Case
