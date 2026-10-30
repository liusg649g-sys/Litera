import { reactive } from 'vue'
import { api, ApiError } from '../api'
import { isReaderContextCurrent, readerContext, type ReaderContext } from './context'

export type QaMode = 'question' | 'summary' | 'analysis'
export type QaIntent = 'question' | 'read-speed' | 'summary' | 'innovation' | 'method' | 'conclusion'
export type QaSectionKey = 'background' | 'method' | 'results' | 'conclusion'
export interface QaCitation { citationId: string; documentId: string; extractionVersion: string; chunkId: string; pageNumber: number; quote: string }
export interface QaSection { key: QaSectionKey; title: string; text: string; citations: QaCitation[] }
export interface QaAnswer {
  answerId: string; answerRevision: number; mode: QaMode; intent: QaIntent; question: string
  answer: string; status: 'answered' | 'insufficient_evidence'; citations: QaCitation[]
  extractionVersion: string; model: string; cached: boolean; createdAt: string; sections?: QaSection[]
}
export interface QaError { status: number; code: string; message: string }
export interface QaMessage {
  id: number; mode: QaMode; intent: QaIntent; question: string
  answer: QaAnswer | null; error: QaError | null; loading: boolean; pageNumber: number | null
}
export interface QaBody { mode: QaMode; question?: string; intent: QaIntent; pageNumber?: number; contextRevision: number }
type Send = (documentId: string, body: QaBody, signal: AbortSignal) => Promise<QaAnswer>

export const NOT_FOUND_SECTION = '未找到对应证据'
export const QUESTION_LIMIT = 6000
const REQUEST_TIMEOUT = 90_000
const ERROR_TEXT: Record<string, string> = {
  EXTRACTION_NOT_READY: '当前文献尚未完成正文提取，请稍后再试。',
  QA_INDEX_BUILDING: '阅读助手索引正在构建，请稍后再试。',
  QA_INDEX_FAILED: '阅读助手索引构建失败，请稍后重试。',
  MODEL_TIMEOUT: '模型响应超时，请重试。',
  MODEL_BUSY: '模型繁忙，请稍后重试。',
  MODEL_QUOTA_LIMITED: '模型额度不足或限流，请稍后重试。',
  MODEL_NOT_CONFIGURED: '阅读助手模型尚未配置，请联系管理员。',
  MODEL_FAILED: '模型返回内容无法解析，请重试。',
  QA_QUESTION_REQUIRED: '请先输入问题。',
}
export function qaErrorText(error: QaError) {
  return error.message || ERROR_TEXT[error.code] || '问答失败，请稍后重试。'
}

export function createQa(send: Send) {
  // Collapsing the panel never resets this object, so a reopened assistant shows
  // the last answer without issuing another paid request.
  const state = reactive({
    documentId: '', open: false, question: '', mode: 'question' as QaMode,
    messages: [] as QaMessage[], loading: false, error: null as QaError | null,
  })
  let epoch = 0, sequence = 0, active: AbortController | null = null
  let timedOut = false

  const abort = () => { active?.abort(); active = null; state.loading = false }

  function reset() {
    epoch++; abort()
    state.messages = []; state.question = ''; state.mode = 'question'
    state.loading = false; state.error = null
  }

  function context(value: Readonly<ReaderContext> | null) {
    const id = value?.documentId ?? ''
    // A document switch (tab/library/deletion) clears the old answer; it must
    // never be labelled as the current document.
    if (id !== state.documentId) { reset(); state.documentId = id }
  }

  async function ask(mode: QaMode, rawQuestion: string, intent: QaIntent, pageNumber?: number, retryOf?: QaMessage) {
    const question = rawQuestion.trim()
    if (mode === 'question' && !question) { state.error = { status: 422, code: 'QA_QUESTION_REQUIRED', message: '请先输入问题。' }; return }
    const documentId = state.documentId
    if (!documentId) { state.error = { status: 0, code: 'READER_UNAVAILABLE', message: '请先打开文献。' }; return }
    const contextRevision = readerRevision()
    if (retryOf) retryOf.loading = true
    let message: QaMessage = retryOf || { id: ++sequence, mode, intent, question, answer: null, error: null, loading: true, pageNumber: pageNumber ?? null }
    // Mutations must go through the reactive proxy: state.messages wraps raw
    // objects on read, so writing to the raw object would never fire watchers.
    if (!retryOf) { state.messages.push(message); message = state.messages[state.messages.length - 1] }
    abort()
    const controller = new AbortController(); active = controller
    const jobEpoch = epoch
    state.mode = mode; state.loading = true; state.error = null
    timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, REQUEST_TIMEOUT)
    try {
      const body: QaBody = { mode, intent, contextRevision }
      if (mode === 'question') body.question = question.slice(0, QUESTION_LIMIT)
      if (mode === 'question' && pageNumber) body.pageNumber = pageNumber
      const answer = await send(documentId, body, controller.signal)
      if (jobEpoch !== epoch) return
      // A page-limited answer is only valid for the revision it was asked from;
      // document-wide answers survive ordinary paging/selection, but a document
      // switch, tab change or deletion invalidates them.
      const pageScoped = mode === 'question' && !!pageNumber
      if (documentId !== state.documentId
        || (readerContext.value?.documentId ?? '') !== documentId
        || (pageScoped && !isReaderContextCurrent({ documentId, contextRevision }))) {
        if (!retryOf) state.messages = state.messages.filter(item => item.id !== message.id)
        return
      }
      message.answer = answer; message.error = null
    } catch (error) {
      if (jobEpoch !== epoch) return
      const aborted = controller.signal.aborted && !(error instanceof ApiError)
      message.error = error instanceof ApiError
        ? { status: error.status, code: error.code, message: qaErrorText({ status: error.status, code: error.code, message: error.message }) }
        : aborted
          ? timedOut
            ? { status: 504, code: 'MODEL_TIMEOUT', message: ERROR_TEXT.MODEL_TIMEOUT! }
            : { status: 0, code: 'CANCELLED', message: '已取消本次提问。' }
          : { status: 0, code: 'NETWORK_ERROR', message: '问答请求失败，请检查网络后重试。' }
      if (!retryOf) state.error = message.error
    } finally {
      clearTimeout(timer)
      message.loading = false
      if (active === controller) { active = null; state.loading = false }
    }
  }

  return {
    state,
    context, reset,
    setOpen(open: boolean) { state.open = open },
    toggle() { state.open = !state.open },
    askQuestion(question: string, pageNumber?: number) { return ask('question', question, 'question', pageNumber) },
    summarize(intent: QaIntent = 'read-speed') { return ask('summary', '', intent) },
    analyze(intent: QaIntent = 'method') { return ask('analysis', '', intent) },
    retry(message: QaMessage) { return ask(message.mode, message.question, message.intent, message.pageNumber ?? undefined, message) },
    cancel() { active?.abort() },
    clearError() { state.error = null },
    dispose() { epoch++; abort(); state.documentId = ''; state.open = false; reset() },
  }
}

// ReaderContext is the single source of truth; callers must not invent a revision.
function readerRevision() {
  return readerContext.value?.contextRevision ?? 0
}
