. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'auth-logout-invalid'
$email = "apitest-$([guid]::NewGuid().ToString('N').Substring(0,8))@example.com"
Send-Json $null 'POST' "$script:Base/auth/register" @{ email = $email; password = 'Apitest-12345!'; displayName = 'apitest' } | Out-Null
# Fresh jar (bypass session cache: logout must kill THIS session)
$jar = Join-Path $env:TEMP ("apitest-" + [guid]::NewGuid().ToString('N') + '.jar')
$tmp = Write-JsonTmp @{ email = $email; password = 'Apitest-12345!' }
$r = Invoke-Curl @('-c', $jar, '-H', "Origin: $script:Origin", '-H', 'Content-Type: application/json', '--data-binary', "@$tmp", "$script:Base/auth/login")
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
$csrf = ($r.Text | ConvertFrom-Json).csrfToken
$out = Invoke-Curl @('-b', $jar, '-X', 'POST', '-H', "Origin: $script:Origin", '-H', "x-csrf-token: $csrf", "$script:Base/auth/logout")
Check 'logout 204' $out.Status 204
$after = Invoke-Curl @('-b', $jar, '-H', "Origin: $script:Origin", "$script:Base/documents")
Check 'session dead after logout -> 401' $after.Status 401
Complete-Case
