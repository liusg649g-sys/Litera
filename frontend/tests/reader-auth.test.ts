import { beforeEach, expect, it, vi } from 'vitest'
import { auth, clearAuth, restoreSession } from '../src/auth'
import { readerTabs, openReaderTab } from '../src/reader/state'
beforeEach(() => {clearAuth();vi.unstubAllGlobals()})
it('clears private tab titles on logout or invalid session', () => {
  openReaderTab('private','Private paper');clearAuth();expect(readerTabs).toHaveLength(0)
})
it('clears previous owners tabs when cookie session switches account',async()=>{
  auth.user={id:'a',email:'a@example.com',displayName:'a',createdAt:''}
  openReaderTab('private','Private paper')
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({user:{id:'b',email:'b@example.com',displayName:'b',createdAt:''},csrfToken:'b-csrf'}))))
  await restoreSession();expect(readerTabs).toHaveLength(0);expect(auth.user?.id).toBe('b')
})
