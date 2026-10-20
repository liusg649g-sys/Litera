import { beforeEach,afterEach,expect,it,vi } from 'vitest'
import { commentPopup,showComment,leaveComment,dismissComment,clearComment } from '../src/reader/commentPopup'
beforeEach(()=>{vi.useFakeTimers();clearComment()})
afterEach(()=>{clearComment();vi.useRealTimers()})
it('hover opens, leave closes, and retains its anchor for the 100ms exit animation',()=>{
  const anchor=document.createElement('div');showComment('a','中文\nsecond',anchor)
  expect(commentPopup.open).toBe(true);expect(commentPopup.content).toBe('中文\nsecond')
  leaveComment('a');expect(commentPopup.open).toBe(false)
  vi.advanceTimersByTime(99);expect(commentPopup.anchor).toBe(anchor)
  vi.advanceTimersByTime(1);expect(commentPopup.anchor).toBeUndefined()
})
it('click pins the bubble, pointer leave and other hovers do not replace it, dismissal closes it',()=>{
  const anchor=document.createElement('div');showComment('a','fixed',anchor,true)
  leaveComment('a');showComment('b','other',document.createElement('div'))
  expect(commentPopup).toMatchObject({open:true,pinned:true,key:'a',content:'fixed'})
  dismissComment();expect(commentPopup.open).toBe(false)
})
it('a rapid re-entry cancels stale cleanup; switching document clears pinned data immediately',()=>{
  const anchor=document.createElement('div');showComment('a','old',anchor);leaveComment('a')
  vi.advanceTimersByTime(50);showComment('b','new',anchor,true);vi.advanceTimersByTime(100)
  expect(commentPopup).toMatchObject({open:true,key:'b',content:'new'})
  clearComment();expect(commentPopup).toMatchObject({open:false,key:'',content:'',anchor:undefined})
})
