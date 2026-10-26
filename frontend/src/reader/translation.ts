import { reactive } from 'vue'
import { textHasUnmappedCharacters, unreliableTextMessage } from './textQuality'
import type { ReaderContext, SelectionPosition } from './context'
import type { TranslationProof } from '../notes/captures'
export interface TranslationSource { documentId: string; pageNumber: number; contextRevision: number; text: string; positions: SelectionPosition[]; textExtractionIssue?: string | null }
export interface TranslationResult { modelConfiguration?: {source:'user'|'mock'|'developer';revision?:string}; translationProof?: TranslationProof; originalText: string; translatedText: string; modelInputText?: string; normalizationCount?: number; source: { documentId: string; pageNumber: number; contextRevision: number; sourceLanguage: string; targetLanguage: string; sourceType: 'translation' } }
type Send = (source: TranslationSource, direction: string, signal: AbortSignal, modelSource?: 'developer'|'user'|'mock', modelRevision?: string) => Promise<TranslationResult>
interface TranslationJob {
  key: string; token: number; epoch: number; source: TranslationSource; direction: string
  modelSource: 'developer'|'user'|'mock'; modelRevision: string; controller: AbortController; promise: Promise<void>; finish: () => void
}
export function createTranslation(send: Send) {
  const state = reactive({ modelSource: 'developer' as 'developer'|'user'|'mock', modelRevision: '', resultModelKey: '', open: false, mode: 'manual', direction: 'en-zh', source: null as TranslationSource | null, result: null as TranslationResult | null, resultPositions: [] as SelectionPosition[], loading: false, queued: false, autoPaused: false, error: '', dragging: false })
  let timer: ReturnType<typeof setTimeout> | undefined, revision = 0, epoch = 0, lastKey = '', activeDocument = ''
  let active: TranslationJob | null = null, pending: TranslationJob | null = null
  const saved = new Map<string, {source: TranslationSource | null; result: TranslationResult | null; resultPositions: SelectionPosition[]; error: string}>()
  function key() { return JSON.stringify([state.source?.documentId,state.source?.pageNumber,state.source?.text,state.source?.positions,state.direction,state.modelSource,state.modelRevision]) }
  function busy() { state.loading = !!(active || pending); state.queued = !!pending }
  function dropPending() { const job=pending; pending=null; job?.finish(); busy() }
  function invalidate(abort = false) {
    clearTimeout(timer); revision++; dropPending()
    if(active) { lastKey = ''; if(abort) active.controller.abort() }
    // Aborting fetch is not proof that the transport/server has finished.
    // Keep the active slot until its promise settles before sending another job.
    busy()
  }
  function schedule() { clearTimeout(timer); if(state.open && !state.autoPaused && state.mode === 'realtime' && state.source && !state.dragging && !state.source.textExtractionIssue && !textHasUnmappedCharacters(state.source.text) && key() !== lastKey) timer = setTimeout(() => { void request(false) }, 500) }
  function context(value: Readonly<ReaderContext> | null) {
    if (!value) { invalidate(true); activeDocument = ''; return }
    if (value.documentId !== activeDocument) {
      if (state.source) saved.set(state.source.documentId, {source: structuredClone(JSON.parse(JSON.stringify(state.source))),result: state.result ? JSON.parse(JSON.stringify(state.result)) : null,resultPositions: JSON.parse(JSON.stringify(state.resultPositions)),error: state.error})
      invalidate(true); activeDocument = value.documentId; lastKey = ''
      const previous = saved.get(activeDocument)
      state.source = previous?.source ?? null; state.result = previous?.result ?? null; state.resultPositions = previous?.resultPositions ?? []; state.error = previous?.error ?? ''
      if(saved.size > 12) saved.delete(saved.keys().next().value!)
    }
    if (!value.selectedText.trim() || !value.selectionPosition?.length) { clearTimeout(timer); dropPending(); return }
    const source: TranslationSource = {documentId: value.documentId,pageNumber: value.selectionPosition[0]!.pageNumber,contextRevision: value.contextRevision,textExtractionIssue: value.textExtractionIssue,text: value.selectedText,positions: JSON.parse(JSON.stringify(value.selectionPosition))}
    if (JSON.stringify([source.documentId,source.text,source.positions,source.textExtractionIssue ?? null]) === JSON.stringify([state.source?.documentId,state.source?.text,state.source?.positions,state.source?.textExtractionIssue ?? null])) return
    // Selection changes invalidate the response but do not repeatedly restart a
    // paid model request. After 500ms only the latest stable selection is queued.
    invalidate(); state.source = source; state.error = source.textExtractionIssue || (textHasUnmappedCharacters(source.text) ? unreliableTextMessage : ''); schedule()
  }
  async function run(job: TranslationJob) {
    active=job; state.error=''; lastKey=job.key; busy()
    try {
      const result = await send(job.source, job.direction, job.controller.signal, job.modelSource, job.modelRevision)
      if(job.epoch !== epoch || job.token !== revision) return
      const [from,to] = job.direction.split('-')
      if(result.originalText !== job.source.text || result.source.documentId !== job.source.documentId || result.source.pageNumber !== job.source.pageNumber || result.source.contextRevision !== job.source.contextRevision || result.source.sourceLanguage !== from || result.source.targetLanguage !== to) {
        throw new Error('翻译响应来源不匹配，请重试；当前选区已保留。')
      }
      if(job.modelSource==='user' && (result.modelConfiguration?.source!=='user' || result.modelConfiguration.revision!==job.modelRevision)) throw new Error('模型配置响应不匹配，请重新加载后翻译。')
      if(job.modelSource==='mock' && (result.modelConfiguration?.source!=='mock' || result.translationProof?.provenance!=='isolated_mock')) throw new Error('模拟翻译来源不匹配，未采用结果。')
      state.resultModelKey = JSON.stringify([job.modelSource,job.modelRevision]); state.result = result; state.resultPositions = job.source.positions
    } catch(error) {
      // A rate limit belongs to this authenticated lifetime, not a later user.
      if(job.epoch !== epoch) return
      const limited = typeof error === 'object' && error !== null && 'status' in error && error.status === 429
      if(limited) { clearTimeout(timer); dropPending(); state.autoPaused=true }
      if(job.token === revision || (limited && !state.source?.textExtractionIssue && !textHasUnmappedCharacters(state.source?.text || ''))) state.error = error instanceof Error ? error.message : '翻译失败，请重试'
    } finally {
      active=null
      const next=pending; pending=null; busy()
      job.finish()
      if(next) {
        if(next.epoch === epoch && next.token === revision && next.key === key() && state.open && !state.dragging) void run(next)
        else next.finish()
      }
    }
  }
  function request(explicit = true): Promise<void> {
    if(explicit) {state.open = true; state.autoPaused=false}
    if(!explicit && state.autoPaused) return Promise.resolve()
    clearTimeout(timer)
    if(!state.source || state.source.documentId !== activeDocument) { state.error = '请先在 PDF 正文文字层选中文字；扫描页无文字层时无法选区翻译。'; return Promise.resolve() }
    if(state.source.textExtractionIssue || textHasUnmappedCharacters(state.source.text)) {state.error = state.source.textExtractionIssue || unreliableTextMessage;return Promise.resolve()}
    if(state.source.text.length > 6000) {state.error = '单次最多翻译 6000 个字符，请缩小选区。';return Promise.resolve()}
    const currentKey=key()
    if(active?.key === currentKey && active.token === revision && !active.controller.signal.aborted) return active.promise
    if(pending?.key === currentKey && pending.token === revision) return pending.promise
    if(!explicit && currentKey === lastKey) return Promise.resolve()
    let finish!: () => void
    const promise=new Promise<void>(resolve=>{finish=resolve})
    const job: TranslationJob = {key:currentKey,token:revision,epoch,source:JSON.parse(JSON.stringify(state.source)),direction:state.direction,modelSource:state.modelSource,modelRevision:state.modelRevision,controller:new AbortController(),promise,finish}
    state.error=''
    if(active) { dropPending(); pending=job; busy() }
    else void run(job)
    return promise
  }
  return {state,context,request,
    setModel(source: 'developer'|'user'|'mock', modelRevision='') {if(state.modelSource===source && state.modelRevision===modelRevision)return;invalidate(true);state.modelSource=source;state.modelRevision=modelRevision;lastKey='';state.autoPaused=false},
    setOpen(open: boolean) {state.open=open;if(!open)invalidate(true);else schedule()},
    setMode(mode: string) {if(state.mode===mode)return;state.mode=mode;clearTimeout(timer);dropPending();schedule()},
    setDirection(direction: string) {if(state.direction===direction)return;state.direction=direction;lastKey='';invalidate();schedule()},
    drag(activeDrag: boolean) {state.dragging=activeDrag;if(activeDrag){clearTimeout(timer);dropPending()}else schedule()},
    dispose() {epoch++;invalidate(true);activeDocument='';lastKey='';saved.clear();state.source=null;state.result=null;state.resultPositions=[];state.error='';state.autoPaused=false;state.open=false;state.mode='manual';state.modelSource='developer';state.modelRevision='';state.resultModelKey='';state.dragging=false},
  }
}
