. "$PSScriptRoot\..\lib\common.ps1"
. "$PSScriptRoot\..\lib\fixtures.ps1"
$global:CaseName = 'trans-selection'
$c = Require-AccountA
$pdf = New-Variant (Fixture-Path 'normal.pdf') ([guid]::NewGuid().ToString('N').Substring(0, 6))
$up = Upload-Pdf $c $pdf
$id = ($up.Text | ConvertFrom-Json).id
$body = @{ text = 'The zebra-telegraph method is a deterministic test technique.'
    sourceLanguage = 'en'; targetLanguage = 'zh'; pageNumber = 1; contextRevision = 0 }
$r = Retry-On-Quota { Api-Req $c 'POST' "/documents/$id/translations" $body } 120 10
Check 'translate 200 (retries upstream 429)' $r.Status 200
$j = $r.Text | ConvertFrom-Json
Check-True 'translatedText non-empty' ($j.translatedText -and $j.translatedText.Length -gt 3) ''
Check-True 'result contains CJK characters' ($j.translatedText -match '\p{IsCJKUnifiedIdeographs}') ''
Check-True 'source echoes page/context revision' ($j.source.pageNumber -eq 1 -and $j.source.contextRevision -eq 0) ''
$bad = Api-Req $c 'POST' "/documents/$id/translations" @{ text = 'same'; sourceLanguage = 'en'; targetLanguage = 'en'; pageNumber = 1; contextRevision = 0 }
Check-Match 'same source/target rejected -> 4xx' "$($bad.Status)" '^4\d\d$'
Remove-Doc $c $id
Complete-Case
