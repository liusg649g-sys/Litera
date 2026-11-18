# Invalid parameter business validation -> 400 (not Pydantic 422)
. "$PSScriptRoot\..\lib\common.ps1"
$global:CaseName = 'x-invalid-param-400'
$cfg = Get-Config
if (-not $cfg.EmailA) { Write-Host 'missing account A'; exit 2 }
$c = New-Client $cfg.EmailA $cfg.PassA

# Wrong current password -> 400 INVALID_CURRENT_PASSWORD
$r = Api-Req $c 'POST' '/auth/password' @{
    currentPassword = 'definitely-wrong-password'
    newPassword = 'another-password-123'
}
Check 'wrong current password -> 400' 400 $r.Status
Check-True 'code INVALID_CURRENT_PASSWORD' ($r.Text -match '"code"\s*:\s*"INVALID_CURRENT_PASSWORD"') $r.Text

# New password equals current password -> 400 PASSWORD_UNCHANGED, no actual change
$r2 = Api-Req $c 'POST' '/auth/password' @{
    currentPassword = $cfg.PassA
    newPassword = $cfg.PassA
}
Check 'same password -> 400' 400 $r2.Status
Check-True 'code PASSWORD_UNCHANGED' ($r2.Text -match '"code"\s*:\s*"PASSWORD_UNCHANGED"') $r2.Text

Complete-Case
