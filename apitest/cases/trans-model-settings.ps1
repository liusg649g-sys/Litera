. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'trans-model-settings'
$c = Require-AccountA
$g = Api-Req $c 'GET' '/user-model'
Check-Match 'GET /user-model 2xx or 404-disabled' "$($g.Status)" '^(2\d\d|404)$'
if ($g.Status -eq 200) {
    Check-True 'api key never returned in plaintext' ($g.Text -notmatch '"apiKey"\s*:\s*"(?!.*\*)[^*]{8,}"') 'only masked or absent'
}
Complete-Case
