# apitest/lib/common.ps1 -- shared helpers, dot-sourced by every case.
# Pure ASCII on purpose: PowerShell 5.1 misreads UTF-8-no-BOM scripts.
$ErrorActionPreference = 'Stop'
$script:Base = if ($env:APITEST_BASE) { $env:APITEST_BASE.TrimEnd('/') } else { 'http://localhost:8085/api/v1' }
$script:Origin = ($script:Base -replace '/api/v1$','')
$script:Failures = 0
$script:Checks = 0
$global:CaseName = 'unnamed'

function Get-Config {
    $cfg = @{ EmailA=$env:APITEST_EMAIL; PassA=$env:APITEST_PASSWORD; EmailB=$env:APITEST_EMAIL_B; PassB=$env:APITEST_PASSWORD_B }
    $local = Join-Path $PSScriptRoot '..\config.local.ps1'
    if (Test-Path $local) {
        . $local
        if ($CfgEmailA) { $cfg.EmailA = $CfgEmailA }; if ($CfgPassA) { $cfg.PassA = $CfgPassA }
        if ($CfgEmailB) { $cfg.EmailB = $CfgEmailB }; if ($CfgPassB) { $cfg.PassB = $CfgPassB }
    }
    return $cfg
}

function Invoke-Curl {
    param([string[]]$CurlArgs)
    $out = (& curl.exe -s -w "`n%{http_code}" @CurlArgs 2>&1 | Out-String) -replace "`r", ""
    $out = $out.TrimEnd("`n")
    $idx = $out.LastIndexOf("`n")
    if ($idx -lt 0) { return @{ Status = 0; Text = $out } }
    $status = 0
    [int]::TryParse($out.Substring($idx + 1).Trim(), [ref]$status) | Out-Null
    $text = $out.Substring(0, $idx)
    return @{ Status = $status; Text = $text }
}

function Send-Json {
    # Body goes through a temp file: PowerShell 5.1 mangles embedded quotes in native-exe args.
    param($Client, [string]$Method, [string]$Url, $Body)
    $tmp = Join-Path $env:TEMP ("apitest-body-" + [guid]::NewGuid().ToString('N') + '.json')
    [System.IO.File]::WriteAllText($tmp, ($Body | ConvertTo-Json -Compress -Depth 10))
    $a = @('-X', $Method, '-H', "Origin: $script:Origin", '-H', 'Content-Type: application/json', '--data-binary', "@$tmp")
    if ($Client) {
        $a += @('-b', $Client.Jar)
        if ($Method -ne 'GET') { $a += @('-H', "x-csrf-token: $($Client.Csrf)") }
    }
    $r = Invoke-Curl ($a + @($Url))
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    return $r
}

function Write-JsonTmp {
    param($Body)
    $tmp = Join-Path $env:TEMP ("apitest-body-" + [guid]::NewGuid().ToString('N') + '.json')
    [System.IO.File]::WriteAllText($tmp, ($Body | ConvertTo-Json -Compress -Depth 10))
    return $tmp
}

function New-Client {
    param([string]$Email, [string]$Password)
    # Session cache: auth is rate-limited (20/min); reuse jar+csrf across case processes for 10 min.
    $key = ($Email -replace '[^A-Za-z0-9]', '_')
    $cache = Join-Path $env:TEMP "apitest-sess-$key.json"
    if (Test-Path $cache) {
        try {
            $c = Get-Content $cache -Raw | ConvertFrom-Json
            if ((Get-Date) -lt ([DateTime]$c.expires) -and (Test-Path $c.jar)) {
                $probe = Invoke-Curl @('-b', $c.jar, '-H', "Origin: $script:Origin", "$script:Base/auth/session")
                if ($probe.Status -eq 200) { return @{ Jar = $c.jar; Csrf = $c.csrf } }
            }
        } catch { }
    }
    $jar = Join-Path $env:TEMP ("apitest-" + [guid]::NewGuid().ToString('N') + '.jar')
    $tmp = Write-JsonTmp @{ email = $Email; password = $Password }
    $r = Invoke-Curl @('-c', $jar, '-H', "Origin: $script:Origin", '-H', 'Content-Type: application/json', '--data-binary', "@$tmp", "$script:Base/auth/login")
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    if ($r.Status -ne 200) { throw "login failed for ${Email}: $($r.Status) $($r.Text)" }
    $csrf = ($r.Text | ConvertFrom-Json).csrfToken
    @{ jar = $jar; csrf = $csrf; expires = (Get-Date).AddMinutes(10).ToString('o') } | ConvertTo-Json | Set-Content $cache -Encoding ascii
    return @{ Jar = $jar; Csrf = $csrf }
}

function Api-Req {
    param($Client, [string]$Method, [string]$Path, $Body = $null)
    if ($null -ne $Body) { return Send-Json $Client $Method "$script:Base$Path" $Body }
    $a = @('-X', $Method, '-H', "Origin: $script:Origin")
    if ($Client) {
        $a += @('-b', $Client.Jar)
        if ($Method -ne 'GET') { $a += @('-H', "x-csrf-token: $($Client.Csrf)") }
    }
    return Invoke-Curl ($a + @("$script:Base$Path"))
}

function Api-Download {
    param($Client, [string]$Path, [string]$OutFile)
    $a = @('-o', $OutFile)
    if ($Client) { $a += @('-b', $Client.Jar, '-H', "Origin: $script:Origin") }
    $r = Invoke-Curl ($a + @("$script:Base$Path"))
    return $r.Status
}

function Upload-Pdf {
    param($Client, [string]$FilePath)
    return Invoke-Curl @('-b', $Client.Jar, '-H', "Origin: $script:Origin", '-H', "x-csrf-token: $($Client.Csrf)",
        '-F', "file=@$FilePath;type=application/pdf", "$script:Base/documents")
}

function Remove-Doc {
    param($Client, [string]$Id)
    if (-not $Id) { return }
    Api-Req $Client 'DELETE' "/documents/$Id" | Out-Null
    Api-Req $Client 'DELETE' "/trash/documents/$Id" | Out-Null
}

function Ask-Qa {
    # 503 = QA_INDEX_BUILDING until the embedding sweep finishes.
    # 429 = upstream MODEL_QUOTA; retry instead of reporting a product failure.
    param($Client, [string]$Id, [string]$Question, [int]$TimeoutSec = 240)
    $t0 = Get-Date
    $last = $null
    while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
        $last = Api-Req $Client 'POST' "/documents/$Id/qa" @{ mode = 'question'; question = $Question; contextRevision = 0 }
        if ($last.Status -eq 200) { return $last }
        if ($last.Status -ne 429 -and $last.Status -ne 503) { return $last }
        Start-Sleep -Seconds 10
    }
    return $last
}

function Retry-On-Quota {
    # Wrap a call that may hit upstream 429; keeps retrying until 200 or timeout.
    param([scriptblock]$Call, [int]$TimeoutSec = 120, [int]$IntervalSec = 10)
    $t0 = Get-Date
    $r = $null
    while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
        $r = & $Call
        if ($r.Status -eq 200) { return $r }
        if ($r.Status -ne 429) { return $r }
        Start-Sleep -Seconds $IntervalSec
    }
    return $r
}

function Wait-DocStatus {
    param($Client, [string]$Id, [string]$Want, [int]$TimeoutSec = 90)
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
        $r = Api-Req $Client 'GET' "/documents/$Id"
        if ($r.Status -eq 200) {
            $j = $r.Text | ConvertFrom-Json
            if ($j.parseStatus -eq $Want) { return $j }
            if ($j.parseStatus -eq 'failed' -and $Want -ne 'failed') { return $j }
        }
        Start-Sleep -Seconds 3
    }
    return $null
}

function Check {
    param([string]$Name, $Actual, $Expected)
    $script:Checks++
    if ("$Actual" -eq "$Expected") { Write-Host "  [GREEN] $Name expected=$Expected actual=$Actual" }
    else { $script:Failures++; Write-Host "  [RED] $Name expected=$Expected actual=$Actual" }
}

function Check-Match {
    param([string]$Name, [string]$Actual, [string]$Pattern)
    $script:Checks++
    if ($Actual -match $Pattern) { Write-Host "  [GREEN] $Name ~/$Pattern/ actual=$Actual" }
    else { $script:Failures++; Write-Host "  [RED] $Name ~/$Pattern/ actual=$Actual" }
}

function Check-True {
    param([string]$Name, [bool]$Cond, [string]$Detail = '')
    $script:Checks++
    if ($Cond) { Write-Host "  [GREEN] $Name $Detail" } else { $script:Failures++; Write-Host "  [RED] $Name $Detail" }
}

function Complete-Case {
    if ($script:Failures -eq 0) { Write-Host "CASE $global:CaseName GREEN $script:Checks/$script:Checks"; exit 0 }
    Write-Host "CASE $global:CaseName RED failures=$script:Failures/$script:Checks"; exit 1
}

function Skip-Case {
    param([string]$Reason)
    Write-Host "CASE $global:CaseName SKIP $Reason"
    exit 2
}

function Require-AccountA {
    $cfg = Get-Config
    if (-not $cfg.EmailA -or -not $cfg.PassA) { Skip-Case 'no credentials: set APITEST_EMAIL/APITEST_PASSWORD or apitest/config.local.ps1' }
    return New-Client $cfg.EmailA $cfg.PassA
}
