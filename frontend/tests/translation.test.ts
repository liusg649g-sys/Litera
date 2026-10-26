import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {createTranslation,type TranslationResult} from '../src/reader/translation'
import type {ReaderContext} from '../src/reader/context'
function selection(text='first',revision=1,doc='a'):ReaderContext{return {documentId:doc,pageNumber:1,contextRevision:revision,selectedText:text,selectionPosition:[{pageNumber:1,textQuote:text,rects:[{x:.1,y:.1,width:.2,height:.1}]}],annotationId:null}}
function result(text='first',revision=1,page=1,direction='en-zh'):TranslationResult{return {originalText:text,translatedText:'Mock '+text,source:{documentId:'a',pageNumber:page,contextRevision:revision,sourceLanguage:direction.split('-')[0]!,targetLanguage:direction.split('-')[1]!,sourceType:'translation'}}}
describe('selection translation state (Mock model)',()=>{
 beforeEach(()=>vi.useFakeTimers());afterEach(()=>vi.useRealTimers())
 it('manual never requests until explicit click and opens closed panel',async()=>{const send=vi.fn().mockResolvedValue(result());const m=createTranslation(send);m.context(selection());await vi.advanceTimersByTimeAsync(1000);expect(send).not.toHaveBeenCalled();await m.request();expect(send).toHaveBeenCalledOnce();expect(m.state.open).toBe(true)})
 it('direction sent correctly',async()=>{const send=vi.fn().mockResolvedValue(result());const m=createTranslation(send);m.context(selection());m.setDirection('zh-en');await m.request();expect(send.mock.calls[0]![1]).toBe('zh-en')})
 it('realtime waits 500ms, resets on changes, and deduplicates',async()=>{const send=vi.fn().mockResolvedValue(result('last',9));const m=createTranslation(send);m.setOpen(true);m.setMode('realtime');for(let i=0;i<8;i++){m.context(selection('text'+i,i));await vi.advanceTimersByTimeAsync(100)}m.context(selection('last',9));await vi.advanceTimersByTimeAsync(499);expect(send).not.toHaveBeenCalled();await vi.advanceTimersByTimeAsync(1);expect(send).toHaveBeenCalledOnce();m.context(selection('last',10));await vi.advanceTimersByTimeAsync(600);expect(send).toHaveBeenCalledOnce()})
 it('does not send while dragging',async()=>{const send=vi.fn().mockResolvedValue(result());const m=createTranslation(send);m.setOpen(true);m.setMode('realtime');m.drag(true);m.context(selection());await vi.advanceTimersByTimeAsync(1000);expect(send).not.toHaveBeenCalled();m.drag(false);await vi.advanceTimersByTimeAsync(500);expect(send).toHaveBeenCalledOnce()})
 it('invalidates old selection but drains its transport before sending the new request',async()=>{let finish!:(r:TranslationResult)=>void;const send=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>finish=resolve)).mockResolvedValue(result('new',2));const m=createTranslation(send);m.context(selection());const old=m.request();m.context(selection('new',2));expect(send.mock.calls[0]![2].aborted).toBe(false);const next=m.request();expect(send).toHaveBeenCalledOnce();expect(m.state.queued).toBe(true);finish(result());await old;await next;expect(send).toHaveBeenCalledTimes(2);expect(m.state.result?.originalText).toBe('new');expect(m.state.loading).toBe(false)})
 it('collapse pauses auto, preserves direction/mode/result, manual stops auto',async()=>{const send=vi.fn().mockResolvedValue(result());const m=createTranslation(send);m.context(selection());await m.request();m.setMode('realtime');m.setDirection('zh-en');m.setOpen(false);await vi.advanceTimersByTimeAsync(1000);expect(send).toHaveBeenCalledOnce();expect(m.state.result?.translatedText).toBe('Mock first');m.setMode('manual');m.setOpen(true);await vi.advanceTimersByTimeAsync(1000);expect(send).toHaveBeenCalledOnce();expect(m.state.direction).toBe('zh-en')})
 it('failure preserves text, retry succeeds and ordinary input selection ignored',async()=>{const send=vi.fn().mockRejectedValueOnce(new Error('quota')).mockResolvedValue(result());const m=createTranslation(send);m.context(selection());await m.request();expect(m.state.source?.text).toBe('first');expect(m.state.error).toBe('quota');m.context({...selection('input'),selectionPosition:null});expect(m.state.source?.text).toBe('first');await m.request();expect(m.state.result?.translatedText).toBe('Mock first')})
 it('document change invalidates response and restores prior document state',async()=>{const send=vi.fn().mockResolvedValue(result());const m=createTranslation(send);m.context(selection());await m.request();m.context(null);m.context(selection('second',2,'b'));expect(m.state.result).toBeNull();m.context(null);m.context({...selection('',3),selectionPosition:null});expect(m.state.result?.originalText).toBe('first');m.dispose();expect(m.state.result).toBeNull()})
})

it('reopening waits for an aborted transport to settle before resuming realtime',async()=>{vi.useFakeTimers();try{let finish!:(r:TranslationResult)=>void;const send=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>finish=resolve)).mockResolvedValue(result());const m=createTranslation(send);m.context(selection());m.setOpen(true);m.setMode('realtime');await vi.advanceTimersByTimeAsync(500);expect(send).toHaveBeenCalledOnce();m.setOpen(false);expect(send.mock.calls[0]![2].aborted).toBe(true);expect(m.state.loading).toBe(true);m.setOpen(true);await vi.advanceTimersByTimeAsync(500);expect(send).toHaveBeenCalledOnce();expect(m.state.queued).toBe(true);finish(result());await vi.advanceTimersByTimeAsync(0);expect(send).toHaveBeenCalledTimes(2);expect(m.state.result?.originalText).toBe('first');m.dispose()}finally{vi.useRealTimers()}})


it('manual rejects mismatched source without replacing a successful result',async()=>{const send=vi.fn().mockResolvedValueOnce(result()).mockResolvedValue({...result(),source:{...result().source,pageNumber:99}});const m=createTranslation(send);m.context(selection());await m.request();await m.request();expect(m.state.error).toContain('来源不匹配');expect(m.state.result?.source.pageNumber).toBe(1);expect(m.state.source?.text).toBe('first');m.dispose()})
it('same text on another physical page carries the new page and revision',async()=>{const send=vi.fn().mockResolvedValue(result('first',2,2));const m=createTranslation(send);const context=selection('first',2);context.pageNumber=3;context.selectionPosition![0]!.pageNumber=2;m.context(context);await m.request();expect(send.mock.calls[0]![0].pageNumber).toBe(2);expect(m.state.result?.source.pageNumber).toBe(2);m.dispose()})


it('repeated manual clicks share the in-flight promise and allow an explicit retry after completion',async()=>{
  let finish!:(r:TranslationResult)=>void
  const send=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>finish=resolve)).mockResolvedValue(result())
  const m=createTranslation(send);m.context(selection())
  const first=m.request(),duplicate=m.request()
  expect(duplicate).toBe(first);expect(send).toHaveBeenCalledOnce();expect(m.state.loading).toBe(true)
  finish(result());await first
  await m.request();expect(send).toHaveBeenCalledTimes(2);m.dispose()
})

it('realtime sends at most one request and retains only the latest stable candidate',async()=>{
  vi.useFakeTimers()
  try {
    const jobs:{source:Parameters<Parameters<typeof createTranslation>[0]>[0];finish:(r:TranslationResult)=>void}[]=[]
    let concurrency=0,maxConcurrency=0
    const send=vi.fn((source)=>{concurrency++;maxConcurrency=Math.max(maxConcurrency,concurrency);return new Promise<TranslationResult>(resolve=>jobs.push({source,finish:resolve})).finally(()=>{concurrency--})})
    const m=createTranslation(send);m.context(selection());m.setOpen(true);m.setMode('realtime')
    await vi.advanceTimersByTimeAsync(500);expect(send).toHaveBeenCalledOnce()
    m.context(selection('second',2));await vi.advanceTimersByTimeAsync(499)
    expect(m.state.queued).toBe(false);await vi.advanceTimersByTimeAsync(1);expect(m.state.queued).toBe(true)
    m.context(selection('latest',3));await vi.advanceTimersByTimeAsync(500)
    expect(send).toHaveBeenCalledOnce();expect(m.state.queued).toBe(true)
    jobs[0]!.finish(result());await vi.advanceTimersByTimeAsync(0)
    expect(send).toHaveBeenCalledTimes(2);expect(jobs[1]!.source.text).toBe('latest');expect(m.state.result).toBeNull()
    jobs[1]!.finish(result('latest',3));await vi.advanceTimersByTimeAsync(0)
    expect(maxConcurrency).toBe(1);expect(m.state.result?.originalText).toBe('latest');expect(m.state.loading).toBe(false);expect(m.state.queued).toBe(false)
    m.dispose()
  } finally { vi.useRealTimers() }
})

it('manual mode drops pending automatic work without spawning another transport',async()=>{
  vi.useFakeTimers()
  try {
    let finish!:(r:TranslationResult)=>void
    const send=vi.fn().mockImplementation(()=>new Promise(resolve=>finish=resolve))
    const m=createTranslation(send);m.context(selection());m.setOpen(true);m.setMode('realtime')
    await vi.advanceTimersByTimeAsync(500)
    m.context(selection('second',2));await vi.advanceTimersByTimeAsync(500);expect(m.state.queued).toBe(true)
    m.setMode('manual');expect(m.state.queued).toBe(false);expect(m.state.loading).toBe(true)
    finish(result());await vi.advanceTimersByTimeAsync(1000)
    expect(send).toHaveBeenCalledOnce();expect(m.state.result).toBeNull();expect(m.state.loading).toBe(false);m.dispose()
  } finally {vi.useRealTimers()}
})

it('a changed language direction waits for the old job and validates the new response direction',async()=>{
  let finish!:(r:TranslationResult)=>void
  const send=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>finish=resolve)).mockResolvedValue(result('first',1,1,'zh-en'))
  const m=createTranslation(send);m.context(selection());const old=m.request()
  m.setDirection('zh-en');const current=m.request();expect(send).toHaveBeenCalledOnce()
  finish(result());await old;await current
  expect(send.mock.calls[1]![1]).toBe('zh-en');expect(m.state.result?.source.targetLanguage).toBe('en');m.dispose()
})

it('a later reliability warning invalidates active success and blocks all pending sends',async()=>{
  let finish!:(r:TranslationResult)=>void
  const send=vi.fn().mockImplementation(()=>new Promise(resolve=>finish=resolve))
  const m=createTranslation(send);m.context(selection());const old=m.request()
  m.context({...selection('first',2),textExtractionIssue:'Unreliable mapping'})
  await m.request();expect(m.state.queued).toBe(false)
  finish(result());await old
  expect(send).toHaveBeenCalledOnce();expect(m.state.result).toBeNull();expect(m.state.error).toBe('Unreliable mapping');m.dispose()
})


it('a 429 drops pending automatic work and requires an explicit retry to resume',async()=>{
  vi.useFakeTimers()
  try {
    let reject!:(error:Error)=>void
    const send=vi.fn().mockImplementationOnce(()=>new Promise((_resolve,fail)=>{reject=fail})).mockResolvedValue(result('latest',3))
    const m=createTranslation(send);m.context(selection());m.setOpen(true);m.setMode('realtime')
    await vi.advanceTimersByTimeAsync(500)
    m.context(selection('second',2));await vi.advanceTimersByTimeAsync(500);expect(m.state.queued).toBe(true)
    reject(Object.assign(new Error('Gateway quota exceeded'),{status:429}));await vi.advanceTimersByTimeAsync(0)
    expect(m.state.autoPaused).toBe(true);expect(m.state.queued).toBe(false);expect(m.state.loading).toBe(false)
    expect(m.state.error).toBe('Gateway quota exceeded')
    m.context(selection('latest',3));m.setOpen(false);m.setOpen(true);m.setMode('manual');m.setMode('realtime')
    await vi.advanceTimersByTimeAsync(5000);await m.request(false)
    expect(send).toHaveBeenCalledOnce();expect(m.state.autoPaused).toBe(true)
    await m.request();expect(send).toHaveBeenCalledTimes(2);expect(m.state.autoPaused).toBe(false);expect(m.state.result?.originalText).toBe('latest');m.dispose()
  } finally {vi.useRealTimers()}
})


it('changing manual/realtime mode alone never duplicates the same active selection',async()=>{
  vi.useFakeTimers()
  try {
    let finish!:(r:TranslationResult)=>void
    const send=vi.fn().mockImplementation(()=>new Promise(resolve=>finish=resolve))
    const m=createTranslation(send);m.context(selection());const current=m.request()
    m.setMode('realtime');await vi.advanceTimersByTimeAsync(500)
    expect(send).toHaveBeenCalledOnce();expect(m.state.queued).toBe(false)
    m.setMode('manual');finish(result());await current
    expect(m.state.result?.originalText).toBe('first');m.dispose()
  } finally {vi.useRealTimers()}
})


it('a late 429 from a disposed lifetime cannot pause or clear the new user work',async()=>{
  let reject!:(error:Error)=>void
  const currentResult={...result('new user',2),source:{...result('new user',2).source,documentId:'b'}}
  const send=vi.fn().mockImplementationOnce(()=>new Promise((_resolve,fail)=>{reject=fail})).mockResolvedValue(currentResult)
  const m=createTranslation(send);m.context(selection());const old=m.request()
  m.dispose();expect(send.mock.calls[0]![2].aborted).toBe(true)
  m.context(selection('new user',2,'b'));const current=m.request();expect(m.state.queued).toBe(true)
  reject(Object.assign(new Error('Old account quota'),{status:429}));await old;await current
  expect(send).toHaveBeenCalledTimes(2);expect(m.state.autoPaused).toBe(false)
  expect(m.state.error).toBe('');expect(m.state.result?.source.documentId).toBe('b');expect(m.state.result?.originalText).toBe('new user');m.dispose()
})

it('dispose cancels the debounce and never carries realtime auto-send into another user',async()=>{
  vi.useFakeTimers()
  try {
    const send=vi.fn().mockResolvedValue(result())
    const m=createTranslation(send);m.context(selection());m.setOpen(true);m.setMode('realtime')
    await vi.advanceTimersByTimeAsync(499);m.dispose()
    expect(m.state.open).toBe(false);expect(m.state.mode).toBe('manual');expect(m.state.dragging).toBe(false);expect(m.state.resultPositions).toEqual([])
    await vi.advanceTimersByTimeAsync(1000);expect(send).not.toHaveBeenCalled()
    m.context(selection('new user',2,'b'));m.setOpen(true)
    await vi.advanceTimersByTimeAsync(1000);expect(send).not.toHaveBeenCalled();m.dispose()
  } finally {vi.useRealTimers()}
})
