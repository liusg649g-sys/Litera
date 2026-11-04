. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'docs-file-download'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$out = Join-Path $env:TEMP 'apitest-download.pdf'
$code = Api-Download $c "/documents/$id/content" $out
Check 'content 200' $code 200
$bytes = [System.IO.File]::ReadAllBytes($out)
Check-True 'starts with %PDF' ([System.Text.Encoding]::ASCII.GetString($bytes[0..4]) -eq '%PDF-') ''
$anon = Join-Path $env:TEMP 'apitest-anon.pdf'
$codeAnon = Api-Download $null "/documents/$id/content" $anon
Check 'anonymous download 401' $codeAnon 401
Remove-Doc $c $id
Complete-Case
