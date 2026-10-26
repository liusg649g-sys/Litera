import {existsSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import {join} from 'node:path'
export function quoteForShell(value:string,platform:string=process.platform){
 if(platform==='win32'){
  if(/["%\r\n]/.test(value))throw new Error('Unsupported shell metacharacter in test interpreter path')
  return '"'+value+'"'
 }
 return "'"+value.replaceAll("'","'\\''")+"'"
}
export function pythonServer(script:string){
 if(!/^[a-z0-9_-]+\.py$/i.test(script))throw new Error('Only project test scripts are allowed')
 const root=fileURLToPath(new URL('../',import.meta.url))
 const python=process.env.LITERA_TEST_PYTHON||join(root,'backend','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
 if(!existsSync(python))throw new Error('Install backend venv or set LITERA_TEST_PYTHON')
 const target=join(root,'scripts',script)
 if(!existsSync(target))throw new Error('Missing project test server')
 return quoteForShell(python)+' '+quoteForShell(target)
}
