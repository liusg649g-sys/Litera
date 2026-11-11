# INJ-02 XSS: PATCH title with <script>, GET back raw string (frontend escapes via v-text)
. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$cfg = Get-Config
if (-not $cfg.EmailA) { Write-Host 'no account'; exit 2 }
$c = New-Client $cfg.EmailA $cfg.PassA

# upload a fresh document we can PATCH
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$version = ($up.Text | ConvertFrom-Json).version

$xss = '<script>alert(1)</script>'
$r = Api-Req $c 'PATCH' "/documents/$id" @{ title = $xss; version = $version }
Check 'PATCH script-tag title -> 200' $r.Status 200

# GET back -- API returns raw <script> tag, NOT stripped by backend
$g = Api-Req $c 'GET' "/documents/$id"
Check 'GET 200' $g.Status 200
$j = $g.Text | ConvertFrom-Json
Check-True 'title preserved verbatim' ($j.title -eq $xss) "got=[$($j.title)]"

# cleanup
Api-Req $c 'DELETE' "/documents/$id" | Out-Null
Api-Req $c 'DELETE' "/trash/documents/$id" | Out-Null
Write-Host 'INJ02 done'
exit 0
