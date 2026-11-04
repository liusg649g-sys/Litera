. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-manual-retry'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
Wait-DocStatus $c $id 'completed' 120 | Out-Null
$r = Api-Req $c 'POST' "/documents/$id/extract"
Check 'manual extract 200' $r.Status 200
Check-True 'requeued for worker (jobStatus=queued)' ($r.Text -match '"jobStatus":\s*"queued"') $r.Text
$final = Wait-DocStatus $c $id 'completed' 120
Check-True 'settles back to completed' ($null -ne $final -and $final.parseStatus -eq 'completed') "actual=$($final.parseStatus)"
Remove-Doc $c $id
Complete-Case
