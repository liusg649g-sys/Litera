. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'auth-wrong-password-401'
$email = "apitest-$([guid]::NewGuid().ToString('N').Substring(0,8))@example.com"
Send-Json $null 'POST' "$script:Base/auth/register" @{ email = $email; password = 'Apitest-12345!'; displayName = 'apitest' } | Out-Null
$r = Send-Json $null 'POST' "$script:Base/auth/login" @{ email = $email; password = 'wrong-password-999' }
Check 'wrong password 401' $r.Status 401
Check-True 'error code INVALID_CREDENTIALS' ($r.Text -match 'INVALID_CREDENTIALS') ''
Complete-Case
