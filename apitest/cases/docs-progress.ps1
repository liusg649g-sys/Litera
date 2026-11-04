. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-progress'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$p = Api-Req $c 'PUT' "/documents/$id/progress" @{ pageNumber = 2; recordOpen = $true; version = 0 }
Check-Match 'PUT progress 2xx' "$($p.Status)" '^2\d\d$'
$g = Api-Req $c 'GET' "/documents/$id/progress"
Check 'GET progress 200' $g.Status 200
Check-True 'pageNumber persisted=2' ($g.Text -match '"pageNumber":\s*2') $g.Text
Remove-Doc $c $id
Complete-Case
