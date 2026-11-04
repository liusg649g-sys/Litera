. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-stop-start'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Skip-Case 'needs docker CLI on host' }
docker compose ps extraction-worker 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Skip-Case 'docker compose stack not reachable from host' }
$c = Require-AccountA
docker compose stop extraction-worker | Out-Null
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
Check 'submit while consumer down -> 201' $up.Status 201
$id = ($up.Text | ConvertFrom-Json).id
$mid = Api-Req $c 'GET' "/documents/$id"
Check-True 'stays processing (queued for worker), not failed' (($mid.Text | ConvertFrom-Json).parseStatus -eq 'processing') ''
docker compose start extraction-worker | Out-Null
$final = Wait-DocStatus $c $id 'completed' 180
Check-True 'auto-consumed after restart, no resubmit' ($null -ne $final -and $final.parseStatus -eq 'completed') "actual=$($final.parseStatus)"
Remove-Doc $c $id
Complete-Case
