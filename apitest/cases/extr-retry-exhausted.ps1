. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'extr-retry-exhausted'
Skip-Case 'needs a forced LLM failure (break AI_API_KEY) to observe 5s/10s/20s backoff then failed; do it in a dedicated session, not in the green-path suite.'
