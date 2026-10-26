param([ValidateSet('status','build','start','logs','test')][string]$Action='status')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
 $composeArgs=@('compose','-p','litera-dev','-f','compose.yaml','-f','compose.dev.yaml')
 switch($Action){
  'status' { & docker @composeArgs ps }
  'build' { & docker @composeArgs build }
  'start' { & docker @composeArgs up -d --build --wait }
  'logs' { & docker @composeArgs logs --tail=80 api nginx }
  'test' { & docker @composeArgs exec -T -e TEST_DATABASE_URL= api python -m pytest -q }
 }
 if($LASTEXITCODE -ne 0){throw "Docker action failed with exit code $LASTEXITCODE"}
} finally {Pop-Location}
