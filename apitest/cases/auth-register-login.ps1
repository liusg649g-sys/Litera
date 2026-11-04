. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'auth-register-login'
$email = "apitest-$([guid]::NewGuid().ToString('N').Substring(0,8))@example.com"
$pass = "Apitest-$([guid]::NewGuid().ToString('N').Substring(0,10))!"
$r = Send-Json $null 'POST' "$script:Base/auth/register" @{ email = $email; password = $pass; displayName = 'apitest' }
Check 'register returns 201' $r.Status 201
$c = New-Client $email $pass
Check 'login returns session' ($null -ne $c.Csrf) 'True'
$me = Invoke-Curl @('-b', $c.Jar, '-H', "Origin: $script:Origin", "$script:Base/auth/session")
Check 'GET /auth/session 200' $me.Status 200
Check-True 'session email matches' (($me.Text | ConvertFrom-Json).user.email -eq $email) $email
Complete-Case
