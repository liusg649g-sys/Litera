. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'extr-not-requested'
Skip-Case 'needs a legacy document without extractionVersion; every new upload creates one. Provide a fixture id via APITEST_LEGACY_DOC to enable.'
if ($env:APITEST_LEGACY_DOC) {
    $c = Require-AccountA
    $r = Api-Req $c 'GET' "/documents/$env:APITEST_LEGACY_DOC/extraction-candidates"
    Check 'legacy doc -> 200' $r.Status 200
    Check-True 'jobStatus not_requested' ($r.Text -match 'not_requested') ''
    Complete-Case
}
