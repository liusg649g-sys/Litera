. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-upload-rejects'
$c = Require-AccountA
$garbage = New-GarbagePdf
$r = Upload-Pdf $c $garbage
Check 'garbage content as pdf -> 4xx' ($r.Status -ge 400 -and $r.Status -lt 500) 'True'
Write-Host "  info: encrypted/oversize branches are covered by unit tests (validate_pdf, MAX_UPLOAD_BYTES); not exercised here"
Complete-Case
