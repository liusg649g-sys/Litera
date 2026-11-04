. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'extr-p95-concurrency'
$c = Require-AccountA
$times = @(); $ids = @()
foreach ($i in 1..20) {
    $v = New-Variant (Fixture-Path 'normal.pdf') ("p95-$i-" + [guid]::NewGuid().ToString('N').Substring(0, 4))
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $r = Upload-Pdf $c $v
    $sw.Stop()
    if ($r.Status -eq 201) { $ids += ($r.Text | ConvertFrom-Json).id; $times += $sw.Elapsed.TotalSeconds }
    Remove-Item $v -Force
}
Check 'all 20 uploads accepted' $ids.Count 20
$sorted = $times | Sort-Object
$p95 = $sorted[[Math]::Min(18, $sorted.Count - 1)]
$max = $sorted[-1]
Write-Host ("  timings: P50={0:n3}s P95={1:n3}s MAX={2:n3}s" -f $sorted[9], $p95, $max)
Check-True 'P95 <= 0.5s (async submit does not wait for LLM)' ($p95 -le 0.5) ("P95={0:n3}s" -f $p95)
$left = Wait-AllSettled $c $ids 300
Check 'queue drains to completed/failed' $left 0
foreach ($id in $ids) { Remove-Doc $c $id }
Complete-Case
