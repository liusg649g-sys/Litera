import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../src/api'
import { publishContext, readerContext } from '../src/reader/context'
import { createQa, type QaAnswer, type QaBody } from '../src/reader/qa'

function publish(documentId = 'a', pageNumber = 1, selectedText = '') {
  publishContext('context-change', { documentId, pageNumber, selectedText, selectionPosition: null })
}
function answer(overrides: Partial<QaAnswer> = {}): QaAnswer {
  return {
    answerId: 'answer-1', answerRevision: 1, mode: 'question', intent: 'question', question: 'q',
    answer: '依据原文的结论[1]', status: 'answered', citations: [],
    extractionVersion: 'v1', model: 'course-chat', cached: false, createdAt: '2026-10-29T00:00:00Z',
    ...overrides,
  }
}
function setup(send: (documentId: string, body: QaBody, signal: AbortSignal) => Promise<QaAnswer>) {
  const qa = createQa(send)
  return qa
}

beforeEach(() => { publish('a', 1) })

describe('阅读助手状态机', () => {
  it('空问题不发起请求', async () => {
    const send = vi.fn().mockResolvedValue(answer())
    const qa = setup(send); qa.context(readerContext.value)
    await qa.askQuestion('   ')
    expect(send).not.toHaveBeenCalled()
    expect(qa.state.error?.code).toBe('QA_QUESTION_REQUIRED')
  })

  it('请求携带模式、问题、当前页与阅读上下文版本', async () => {
    const send = vi.fn().mockResolvedValue(answer())
    const qa = setup(send); qa.context(readerContext.value)
    qa.state.question = '方法有哪些？'
    await qa.askQuestion('方法有哪些？', 3)
    const body = send.mock.calls[0]![1]
    expect(send.mock.calls[0]![0]).toBe('a')
    expect(body.mode).toBe('question')
    expect(body.question).toBe('方法有哪些？')
    expect(body.pageNumber).toBe(3)
    expect(body.contextRevision).toBe(readerContext.value!.contextRevision)
    expect(qa.state.messages[0]!.answer?.answer).toContain('[1]')
  })

  it('问题超过 6000 字符时截断发送', async () => {
    const send = vi.fn().mockResolvedValue(answer())
    const qa = setup(send); qa.context(readerContext.value)
    await qa.askQuestion('x'.repeat(7000))
    expect(send.mock.calls[0]![1].question!.length).toBe(6000)
  })

  it('切换到其他文献后丢弃返回的旧答案', async () => {
    let finish!: (value: QaAnswer) => void
    const send = vi.fn(() => new Promise<QaAnswer>(resolve => { finish = resolve }))
    const qa = setup(send); qa.context(readerContext.value)
    const pending = qa.askQuestion('本文结论是什么？')
    publish('b', 2); qa.context(readerContext.value)
    finish(answer())
    await pending
    expect(qa.state.messages).toHaveLength(0)
    expect(qa.state.documentId).toBe('b')
  })

  it('当前页提问在页码上下文变化后丢弃结果，全文提问保留', async () => {
    let finishPage!: (value: QaAnswer) => void
    const pageSend = vi.fn(() => new Promise<QaAnswer>(resolve => { finishPage = resolve }))
    const pageQa = setup(pageSend); pageQa.context(readerContext.value)
    const pagePending = pageQa.askQuestion('这页讲了什么？', 1)
    publish('a', 2); pageQa.context(readerContext.value)
    finishPage(answer())
    await pagePending
    expect(pageQa.state.messages).toHaveLength(0)

    let finishDoc!: (value: QaAnswer) => void
    const docSend = vi.fn(() => new Promise<QaAnswer>(resolve => { finishDoc = resolve }))
    const docQa = setup(docSend); docQa.context(readerContext.value)
    const docPending = docQa.askQuestion('研究结论是什么？')
    publish('a', 3); docQa.context(readerContext.value)
    finishDoc(answer())
    await docPending
    expect(docQa.state.messages[0]!.answer?.answer).toContain('[1]')
  })

  it('重试复用同一条消息且不重复发送中状态', async () => {
    const send = vi.fn().mockRejectedValueOnce(new ApiError(503, 'QA_INDEX_BUILDING', '索引构建中'))
      .mockResolvedValueOnce(answer())
    const qa = setup(send); qa.context(readerContext.value)
    await qa.askQuestion('q1')
    expect(qa.state.messages).toHaveLength(1)
    expect(qa.state.messages[0]!.error?.message).toBe('索引构建中')
    await qa.retry(qa.state.messages[0]!)
    expect(send).toHaveBeenCalledTimes(2)
    expect(qa.state.messages).toHaveLength(1)
    expect(qa.state.messages[0]!.answer?.answer).toBe(answer().answer)
  })

  it('摘要与结构解析使用对应模式并忽略输入问题', async () => {
    const send = vi.fn().mockResolvedValue(answer({ mode: 'analysis', intent: 'method', cached: true }))
    const qa = setup(send); qa.context(readerContext.value)
    qa.state.question = '不发送'
    await qa.analyze('method')
    expect(send.mock.calls[0]![1].mode).toBe('analysis')
    expect(send.mock.calls[0]![1].question).toBeUndefined()
    expect(qa.state.messages[0]!.answer?.cached).toBe(true)
  })

  it('取消请求标记为已取消并中止传输', async () => {
    const send = vi.fn((_doc: string, _body: QaBody, signal: AbortSignal) => new Promise<QaAnswer>((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')))
    }))
    const qa = setup(send); qa.context(readerContext.value)
    const pending = qa.askQuestion('q')
    expect(send.mock.calls[0]![2].aborted).toBe(false)
    qa.cancel()
    expect(send.mock.calls[0]![2].aborted).toBe(true)
    await pending
    expect(qa.state.messages[0]!.error?.code).toBe('CANCELLED')
    expect(qa.state.loading).toBe(false)
  })
})
