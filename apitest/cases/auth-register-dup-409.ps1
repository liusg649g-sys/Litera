. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'auth-register-dup-409'
$email = "apitest-$([guid]::NewGuid().ToString('N').Substring(0,8))@example.com"
$r1 = Send-Json $null 'POST' "$script:Base/auth/register" @{ email = $email; password = 'Apitest-12345!'; displayName = 'apitest' }
Check 'first register 201' $r1.Status 201
$r2 = Send-Json $null 'POST' "$script:Base/auth/register" @{ email = $email; password = 'Apitest-12345!'; displayName = 'apitest' }
Check 'duplicate register 409' $r2.Status 409
Check-True 'error code EMAIL_EXISTS' ($r2.Text -match 'EMAIL_EXISTS') ''
Complete-Case
