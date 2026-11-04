. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'x-401-matrix'
$targets = @(
    @{ M = 'GET'; P = '/documents' },
    @{ M = 'GET'; P = '/documents/00000000-0000-0000-0000-000000000000' },
    @{ M = 'PATCH'; P = '/documents/00000000-0000-0000-0000-000000000000' },
    @{ M = 'GET'; P = '/documents/00000000-0000-0000-0000-000000000000/extraction-candidates' },
    @{ M = 'GET'; P = '/trash/documents' },
    @{ M = 'GET'; P = '/notes' },
    @{ M = 'POST'; P = '/notes' },
    @{ M = 'POST'; P = '/documents/00000000-0000-0000-0000-000000000000/qa' }
)
foreach ($t in $targets) {
    $r = Api-Req $null $t.M $t.P
    Check "$($t.M) $($t.P) -> 401" $r.Status 401
}
Complete-Case
