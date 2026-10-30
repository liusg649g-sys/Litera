<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ReaderPanel from './ReaderPanel.vue'
import { api } from '../api'
import { auth } from '../auth'
import { createQa, NOT_FOUND_SECTION, QUESTION_LIMIT, type QaAnswer, type QaCitation, type QaMessage } from '../reader/qa'
import { readerContext, subscribeReaderContext } from '../reader/context'
import { navigateReader } from '../reader/navigation'

const qa = createQa((documentId, body, signal) => api<QaAnswer>(`/documents/${encodeURIComponent(documentId)}/qa`, { method: 'POST', signal, body: JSON.stringify(body) }, auth.csrfToken))
const state = qa.state
const emit = defineEmits<{ 'update:open': [boolean] }>()
watch(() => state.open, open => emit('update:open', open))

const messagesEl = ref<HTMLElement>()
const notice = ref('')
const categories = [
  { key: 'read', label: '读懂文献', questions: ['本文主要讲了什么？', '这篇文献试图解决什么问题？', '作者为什么开展这项研究？'] },
  { key: 'method', label: '方法细节', questions: ['本文使用了哪些研究方法？', '实验是如何设计的？', '数据来源和样本是什么？'] },
  { key: 'result', label: '结果与结论', questions: ['本文的主要结果是什么？', '研究结论有哪些？', '研究有哪些局限性？'] },
  { key: 'reference', label: '参考文献', questions: ['本文引用了哪些关键文献？', '这篇文献在相关领域的位置如何？'] },
] as const
const category = ref<typeof categories[number]['key']>('read')
const suggestions = computed(() => categories.find(item => item.key === category.value)?.questions || [])
const hasDocument = computed(() => !!state.documentId)

function fill(text: string) {
  notice.value = ''
  state.question = text.slice(0, QUESTION_LIMIT)
}
function send() {
  notice.value = ''
  const question = state.question.trim()
  if (!question) { notice.value = '请先输入问题。'; return }
  state.question = ''
  void qa.askQuestion(question)
}
async function jump(citation: QaCitation) {
  notice.value = ''
  const result = await navigateReader({ documentId: citation.documentId, pageNumber: citation.pageNumber })
  if (result.status !== 'ok') notice.value = result.message
}

// Position the newest exchange without manual scrolling: when the whole message
// (question + answer) fits the viewport, align its bottom so both are fully
// visible; when it is taller than the viewport, align its top so the question
// is pinned first and the answer continues below.
function focusLatest() {
  const container = messagesEl.value
  const latest = container?.lastElementChild as HTMLElement | null
  if (!container || !latest) return
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const fits = latest.getBoundingClientRect().height <= container.clientHeight
  latest.scrollIntoView({ block: fits ? 'end' : 'start', behavior: reduced ? 'auto' : 'smooth' })
}
watch(() => state.messages.length, () => { void nextTick(focusLatest) })
watch(() => state.messages.at(-1)?.answer ?? state.messages.at(-1)?.error, () => { void nextTick(focusLatest) })

function messageLabel(message: QaMessage) {
  if (message.question) return message.question
  if (message.mode === 'summary') return '文献速读（摘要）'
  if (message.intent === 'method') return '研究方法解析'
  if (message.intent === 'conclusion') return '研究结论解析'
  return '结构解析'
}

const stop = subscribeReaderContext((_event, value) => qa.context(value))
watch(() => auth.user?.id, () => qa.dispose())
function escape(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !state.open) return
  const target = event.target as Element | null
  if (target?.closest?.('dialog[open], .annotation-editor')) return
  qa.setOpen(false)
}
onMounted(() => {
  qa.context(readerContext.value)
  document.addEventListener('keydown', escape)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', escape)
  stop()
  qa.dispose()
})
defineExpose({ toggle: () => qa.setOpen(!state.open), open: () => qa.setOpen(true) })
</script>

<template>
  <ReaderPanel panel-class="qa-panel" :open="state.open" side="right" label="文献阅读助手" :fixed-content="true" :non-modal="true" @close="qa.setOpen(false)">
    <section class="qa-content">
      <div v-if="!state.messages.length" class="qa-welcome">
        <svg class="qa-robot" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="7" width="16" height="12" rx="4" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9" cy="13" r="1.4" fill="currentColor"/><circle cx="15" cy="13" r="1.4" fill="currentColor"/><path d="M12 4v3M9 19v2M15 19v2M2 12h2M20 12h2" stroke="currentColor" stroke-width="1.6"/></svg>
        <h2>你好，我是文献阅读助手</h2>
      </div>

      <div class="qa-tabs" role="tablist" aria-label="建议问题分类">
        <button v-for="item in categories" :key="item.key" role="tab" :aria-selected="category === item.key" :class="{ selected: category === item.key }" @click="category = item.key">{{ item.label }}</button>
      </div>
      <div class="qa-suggestions">
        <button v-for="question in suggestions" :key="question" type="button" :disabled="!hasDocument" @click="fill(question)">{{ question }}</button>
      </div>

      <p v-if="notice" class="qa-notice" role="status">{{ notice }}</p>

      <div ref="messagesEl" class="qa-messages" aria-live="polite">
        <article v-for="message in state.messages" :key="message.id" class="qa-message">
          <p class="qa-question">{{ messageLabel(message) }}<span v-if="message.pageNumber"> · 第 {{ message.pageNumber }} 页</span></p>
          <p v-if="message.loading" class="qa-loading" role="status"><span class="qa-spinner" aria-hidden="true" />正在依据原文生成回答…</p>
          <div v-else-if="message.error" class="qa-error" role="alert">
            <span>{{ message.error.message }}</span>
            <button type="button" @click="qa.retry(message)">重试</button>
          </div>
          <div v-else-if="message.answer" class="qa-answer">
            <p class="qa-disclaimer">AI 生成内容 · 非 PDF 原文，请对照引文核对<span v-if="message.answer.cached"> · 已复用本版本结果</span></p>
            <p v-if="message.answer.status==='insufficient_evidence'" class="qa-insufficient">{{ message.answer.answer }}</p>
            <p v-else class="qa-answer-text">{{ message.answer.answer }}</p>
            <template v-if="message.answer.sections?.length">
              <section v-for="section in message.answer.sections" :key="section.key" class="qa-section">
                <h4>{{ section.title }}</h4>
                <p :class="{ 'qa-insufficient': section.text === NOT_FOUND_SECTION }">{{ section.text }}</p>
                <details v-if="section.citations.length" class="qa-refs">
                  <summary>原文引用（{{ section.citations.length }}）</summary>
                  <ul class="qa-citations">
                    <li v-for="citation in section.citations" :key="citation.citationId">
                      <button type="button" class="qa-page" @click="jump(citation)">第 {{ citation.pageNumber }} 页</button>
                      <q class="qa-quote">{{ citation.quote }}</q>
                    </li>
                  </ul>
                </details>
              </section>
            </template>
            <details v-else-if="message.answer.citations.length" class="qa-refs">
              <summary>原文引用（{{ message.answer.citations.length }}）</summary>
              <ul class="qa-citations">
                <li v-for="citation in message.answer.citations" :key="citation.citationId">
                  <button type="button" class="qa-page" @click="jump(citation)">第 {{ citation.pageNumber }} 页</button>
                  <q class="qa-quote">{{ citation.quote }}</q>
                </li>
              </ul>
            </details>
          </div>
        </article>
      </div>

      <form class="qa-input" @submit.prevent="send">
        <textarea v-model="state.question" :maxlength="QUESTION_LIMIT" rows="3" aria-label="向阅读助手提问" placeholder="围绕当前文献提问…" :disabled="!hasDocument" @keydown.enter.exact.prevent="!$event.isComposing && send()" />
        <div class="qa-input-actions">
          <button v-if="state.loading" type="button" @click="qa.cancel()">取消</button>
          <button v-else type="submit" class="qa-send" :disabled="!hasDocument || !state.question.trim()">发送</button>
        </div>
      </form>
      <p v-if="!hasDocument" class="qa-scope">请先打开一篇文献。</p>
    </section>
  </ReaderPanel>
</template>
