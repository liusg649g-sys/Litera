param([ValidateSet('start','stop','status')][string]$Action='status')
& (Join-Path $PSScriptRoot 'user-model-preview.ps1') $Action
exit $LASTEXITCODE
