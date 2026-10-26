// @vitest-environment node
import {expect,it} from 'vitest'
import {quoteForShell,pythonServer} from '../playwright.server'
it('quotes Windows paths with spaces and rejects interpolation characters',()=>{
 expect(quoteForShell('C:/my project/python.exe','win32')).toBe('"C:/my project/python.exe"')
 expect(()=>quoteForShell('C:/%SECRET%/python.exe','win32')).toThrow()
})
it('quotes POSIX apostrophes without allowing command substitution',()=>{
 expect(quoteForShell("/tmp/user's/python",'linux')).toBe("'/tmp/user'\\''s/python'")
 expect(quoteForShell('/tmp/$(not-executed)/python','linux')).toBe("'/tmp/$(not-executed)/python'")
})
it('does not accept an arbitrary shell script as a test server',()=>{
 expect(()=>pythonServer('../other-project.py')).toThrow()
 expect(()=>pythonServer('api.py; echo unsafe')).toThrow()
})
