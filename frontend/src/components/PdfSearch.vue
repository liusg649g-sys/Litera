<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { findMatches } from '../reader/search'
import type { SearchMatch } from '../reader/search'
const props = defineProps<{ pdf: PDFDocumentProxy; selected: string }>()
const emit = defineEmits<{ matches: [SearchMatch[]]; navigate: [SearchMatch] }>()
const keyword = ref(''), caseSensitive = ref(false), wholeWord = ref(false), results = ref<SearchMatch[]>([])
const busy = ref(false), processed = ref(0), emptyPages = ref(0), error = ref('')
const index = computed(() => results.value.findIndex(r => r.id === props.selected))
let generation = 0, timer: ReturnType<typeof setTimeout> | undefined
function step(direction: number) { if (results.value.length) emit('navigate', results.value[(index.value + direction + results.value.length) % results.value.length]!) }
async function search(token: number) {
  const pdf = props.pdf, query = keyword.value.trim(), sensitive = caseSensitive.value, whole = wholeWord.value
  if (!query) return
  busy.value = true
  const found: SearchMatch[] = []; let empty = 0
  try {
    for (let number = 1; number <= pdf.numPages; number++) {
      if (token !== generation) return
      const page = await pdf.getPage(number), content = await page.getTextContent()
      if (token !== generation) return
      const items = content.items.filter(item => 'str' in item)
      const length = items.reduce((n, item) => n + item.str.length, 0)
      if (length > 500_000) throw new Error('单页文本超过搜索资源限制，请缩小文献后重试。')
      if (!items.some(item => item.str.trim())) empty++
      found.push(...findMatches(items, query, sensitive, whole, number))
      if (found.length > 20_000) throw new Error('匹配超过 20,000 项，请使用更具体的关键词。')
      processed.value = number
      // Yield between pages; never retain an unbounded whole-document text index.
      await new Promise(resolve => setTimeout(resolve, 0))
    }
    if (token !== generation) return
    emptyPages.value = empty; results.value = found; emit('matches', found)
    if (found[0]) emit('navigate', found[0])
  } catch (reason) { if (token === generation) { error.value = reason instanceof Error ? reason.message : '搜索失败，请重新搜索'; results.value = []; emit('matches', []) } }
  finally { if (token === generation) busy.value = false }
}
watch([keyword, caseSensitive, wholeWord, () => props.pdf], () => {
  const token = ++generation; clearTimeout(timer); busy.value = false; error.value = ''; processed.value = 0; results.value = []; emit('matches', [])
  if (keyword.value.trim()) timer = setTimeout(() => { void search(token) }, 250)
})
onBeforeUnmount(() => { generation++; clearTimeout(timer); emit('matches', []) })
</script>
<template>
  <div class="pdf-search">
    <form @submit.prevent="step(1)"><input v-model="keyword" aria-label="PDF 文内搜索" placeholder="搜索 PDF 文本" maxlength="500"><button type="button" aria-label="清除搜索" @click="keyword = ''">×</button></form>
    <div class="search-options"><label><input v-model="caseSensitive" type="checkbox">区分大小写</label><label><input v-model="wholeWord" type="checkbox">全词匹配</label></div>
    <p role="status" aria-live="polite">{{ error || (busy ? `搜索中 ${processed} / ${pdf.numPages} 页` : !keyword.trim() ? '输入关键词搜索真实 PDF 文本' : emptyPages === pdf.numPages ? '此 PDF 无可提取文本，扫描页不支持文本搜索' : `${results.length ? index + 1 : 0} / ${results.length} 个匹配${emptyPages ? `（${emptyPages} 页无文本，仅搜索可提取文本）` : ''}`) }}</p>
    <div><button :disabled="!results.length" aria-label="上一个匹配" @click="step(-1)">↑ 上一个</button><button :disabled="!results.length" aria-label="下一个匹配" @click="step(1)">↓ 下一个</button></div>
    <ol class="search-results"><li v-for="result in results" :key="result.id"><button :class="{ selected: selected === result.id }" @click="emit('navigate', result)"><b>第 {{ result.pageNumber }} 页</b><span>{{ result.snippet }}</span></button></li></ol>
  </div>
</template>
