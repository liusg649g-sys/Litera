# apitest/lib/fixtures.ps1 -- fixture paths, variants, wait helpers. Dot-source after common.ps1.

function Fixture-Path {
    param([string]$Name)
    return (Join-Path $PSScriptRoot "..\fixtures\$Name")
}

function New-Variant {
    param([string]$Src, [string]$Tag)
    $dst = Join-Path $env:TEMP ("apitest-variant-$Tag.pdf")
    $bytes = [System.IO.File]::ReadAllBytes($Src)
    $extra = [System.Text.Encoding]::ASCII.GetBytes("`n% apitest variant $Tag")
    [System.IO.File]::WriteAllBytes($dst, ($bytes + $extra))
    return $dst
}

function New-GarbagePdf {
    $dst = Join-Path $env:TEMP 'apitest-garbage.pdf'
    [System.IO.File]::WriteAllText($dst, 'this is not a pdf at all')
    return $dst
}

function Wait-AllSettled {
    param($Client, [string[]]$Ids, [int]$TimeoutSec = 240)
    $t0 = Get-Date
    $pending = @($Ids)
    while ($pending.Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
        $next = @()
        foreach ($id in $pending) {
            $r = Api-Req $Client 'GET' "/documents/$id"
            if ($r.Status -eq 200) {
                $j = $r.Text | ConvertFrom-Json
                if ($j.parseStatus -ne 'completed' -and $j.parseStatus -ne 'failed') { $next += $id }
            }
        }
        $pending = $next
        if ($pending.Count -gt 0) { Start-Sleep -Seconds 5 }
    }
    return $pending.Count
}
