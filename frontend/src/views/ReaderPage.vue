<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { ArrowLeft, ArrowRight, ArrowDown, Download, Fold, Expand, Search, ChatLineSquare, EditPen, Brush, Picture, CirclePlus, Crop, RefreshLeft, RefreshRight, Delete, Document, MoreFilled } from '@element-plus/icons-vue'
import Brand from '../components/Brand.vue'
import WorkspaceTabs from '../components/WorkspaceTabs.vue'
import PdfPage from '../components/PdfPage.vue'
import ReaderPanel from '../components/ReaderPanel.vue'
import PdfThumbnail from '../components/PdfThumbnail.vue'
import PdfOutline from '../components/PdfOutline.vue'
import type { OutlineNode } from '../components/PdfOutline.vue'
import PdfSearch from '../components/PdfSearch.vue'
import type { SearchMatch } from '../reader/search'
import { createProgress } from '../reader/progress'
import type { ReadingState } from '../reader/progress'
import { clampZoom, fitZoom, PAGE_PADDING, PAGE_GAP } from '../reader/zoom'
import { publishContext, readSelection, readerContext } from '../reader/context'
import { api } from '../api'
import { auth } from '../auth'
import { contentUrl } from '../library'
import type { DocumentDTO } from '../library'
import { readerTabs, openReaderTab, clearReaderTabs, pageGroup, adjacentPage } from '../reader/state'
import type { ViewMode, ZoomMode } from '../reader/state'
import { createPdfTask, pdfError, pdfStatus } from '../reader/pdf'
import '../reader/reader.css'
const route = useRoute(), router = useRouter()
const pdf = shallowRef<PDFDocumentProxy>(), viewport = ref<HTMLElement>()
const keyboardFocus = ref(false)
const loading = ref(true), failure = ref(''), count = ref(0), pageInput = ref('1')
const active = computed(() => readerTabs.find(item => item.id === String(route.params.documentId)))
const current = computed(() => active.value?.page || 1)
const mode = computed(() => active.value?.mode || 'continuous')
const scale = computed(() => active.value?.zoom || 1), zoomInput = ref('100')
const sizes = shallowRef<{ width: number; height: number }[]>([]), outline = shallowRef<OutlineNode[]>([]), outlineError = ref('')
const matches = shallowRef<SearchMatch[]>([]), selectedMatch = ref('')
const matchesByPage = computed(() => { const map = new Map<number, SearchMatch[]>(); for (const match of matches.value) { const list = map.get(match.pageNumber) || []; list.push(match); map.set(match.pageNumber, list) } return map })
const progress = shallowRef<ReturnType<typeof createProgress>>()
const pages = computed(() => pageGroup(current.value, count.value, mode.value))
const leftOpen = ref(false), rightOpen = ref(false), rightPanel = ref('搜索')
const leftPanel = ref('缩略图'), group = ref('阅读'), notice = ref('')
const leftWidth = ref(240)
const tools = {
  '批注': [['高亮', EditPen], ['下划线', EditPen], ['波浪线', EditPen], ['删除线', EditPen], ['注释', ChatLineSquare], ['自由文本', Document], ['手绘', Brush], ['荧光笔', EditPen]],
  '形状': [['矩形', Crop], ['圆形', CirclePlus], ['椭圆形', CirclePlus]],
  '插入': [['签名', EditPen], ['水印', Document], ['图片', Picture]],
} as const
const activeTools = computed(() => group.value === '阅读' ? [] : tools[group.value as keyof typeof tools])
let generation = 0, resource: ReturnType<typeof createPdfTask> | undefined
let metadataRequest: AbortController | undefined
let scrollFrame = 0, leaving = false, fullFallback = false
let layoutFrame = 0, layoutRevision = 0, suppressScroll = false
let resizeObserver: ResizeObserver | undefined, fitRevision = 0, selectionRevision = 0, anchorRevision = 0
const ready = ref(false)
let navigating = false, jumpRevision = 0, loadedDocumentId = ''
function readingState(): ReadingState { return { pageNumber: current.value, zoom: scale.value, zoomMode: active.value?.zoomMode || 'fit-width', viewMode: mode.value } }
function context(event: 'context-change' | 'document-change' | 'selection-change' = 'context-change') {
  publishContext(event, { documentId: String(route.params.documentId), pageNumber: current.value, selectedText: '', selectionPosition: null })
}
function pageReady(number: number) {
  if (number !== current.value || loadedDocumentId !== String(route.params.documentId)) return
  ready.value = true; void progress.value?.ready(readingState())
  if (navigation) void locate()
}
async function beforeLeave() { if (!auth.user) return true; await progress.value?.flush(); return !progress.value?.status.dirty || (!!failure.value && !pdf.value) }
onBeforeRouteLeave(beforeLeave)
onBeforeRouteUpdate(beforeLeave)
watch([group, leftOpen, rightOpen, leftWidth, notice, () => progress.value?.status.error], async () => {
  const root = viewport.value, token = generation, revision = ++layoutRevision, page = current.value, navigationRevision = jumpRevision
  if (!root || !pdf.value) return
  const node = root.querySelector<HTMLElement>(`[data-page="${page}"]`)
  const offset = node ? node.getBoundingClientRect().top - root.getBoundingClientRect().top : 0
  const scrollLeft = root.scrollLeft
  suppressScroll = true; cancelAnimationFrame(scrollFrame); cancelAnimationFrame(layoutFrame)
  await nextTick()
  if (revision !== layoutRevision || token !== generation || leaving) return
  if (page !== current.value || navigationRevision !== jumpRevision) { suppressScroll = false; return }
  if (node?.isConnected) root.scrollTop += node.getBoundingClientRect().top - root.getBoundingClientRect().top - offset
  root.scrollLeft = scrollLeft
  if (active.value) active.value.page = page
  pageInput.value = String(page)
  layoutFrame = requestAnimationFrame(() => { suppressScroll = false })
})
function anchor(x?: number, y?: number) {
  const root = viewport.value
  if (!root) return () => {}
  const bounds = root.getBoundingClientRect(), sx = x ?? bounds.left + root.clientWidth / 2, sy = y ?? bounds.top + root.clientHeight / 2
  const nodes = [...root.querySelectorAll<HTMLElement>('[data-page]')]
  const node = nodes.find(el => { const r = el.getBoundingClientRect(); return r.left <= sx && sx <= r.right && r.top <= sy && sy <= r.bottom }) || nodes.find(el => Number(el.dataset.page) === current.value)
  if (!node) return () => {}
  const rect = node.getBoundingClientRect(), px = (sx - rect.left) / rect.width, py = (sy - rect.top) / rect.height, number = Number(node.dataset.page)
  return () => {
    const target = root.querySelector<HTMLElement>(`[data-page="${number}"]`)
    if (!target) return
    const rect = target.getBoundingClientRect()
    root.scrollLeft += rect.left + rect.width * px - sx; root.scrollTop += rect.top + rect.height * py - sy
  }
}
async function applyScale(value: number, zoomMode: ZoomMode, x?: number, y?: number) {
  if (!active.value || !pdf.value || loadedDocumentId !== String(route.params.documentId)) return
  const restore = navigating ? () => {} : anchor(x, y), token = generation, revision = ++anchorRevision, page = current.value, navigationRevision = jumpRevision
  suppressScroll = true; active.value.zoomMode = zoomMode; active.value.zoom = clampZoom(value)
  zoomInput.value = String(Math.round(active.value.zoom * 10000) / 100)
  window.getSelection()?.removeAllRanges()
  await nextTick()
  if (token !== generation || revision !== anchorRevision) return
  if (navigationRevision !== jumpRevision) { suppressScroll = false; return }
  restore(); active.value!.page = page; pageInput.value = String(page)
  cancelAnimationFrame(layoutFrame); layoutFrame = requestAnimationFrame(() => { suppressScroll = false })
}
function zoom(value: number, x?: number, y?: number) { if (Number.isFinite(value)) void applyScale(value, 'custom', x, y) }
watch(scale, value => { zoomInput.value = String(Math.round(value * 10000) / 100) })
function manualZoom() {
  const raw = zoomInput.value.trim().replace(/%$/, '')
  if (!raw || !Number.isFinite(Number(raw))) { notice.value = '请输入有效的缩放比例'; return }
  const value = Number(raw) / 100
  if (value < .5 || value > 5) notice.value = '缩放范围为 50%–500%，已调整到边界'
  zoom(value)
}
function fit(value?: ZoomMode) {
  const zoomMode = value || active.value?.zoomMode
  if (!pdf.value || loadedDocumentId !== String(route.params.documentId) || !viewport.value || !active.value || !zoomMode || zoomMode === 'custom') return
  const numbers = mode.value === 'spread' ? pageGroup(current.value, count.value, 'spread') : [current.value]
  const selected = numbers.map(n => sizes.value[n - 1]!).filter(Boolean)
  if (!selected.length) return
  const root = viewport.value, next = fitZoom(selected, root.clientWidth, root.clientHeight, zoomMode)
  if (Math.abs(next - scale.value) > .0001 || active.value.zoomMode !== zoomMode) void applyScale(next, zoomMode)
}
function wheel(event: WheelEvent) {
  if (!event.ctrlKey || !pdf.value) return
  event.preventDefault(); zoom(scale.value * Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * .002), event.clientX, event.clientY)
}
watch([current, mode], ([, value], [, previous]) => {
  if (!pdf.value || loadedDocumentId !== String(route.params.documentId)) return
  const selected = readerContext.value
  if (value !== previous) { window.getSelection()?.removeAllRanges(); context() }
  else if (selected?.selectedText) publishContext('context-change', { documentId: selected.documentId, pageNumber: selected.pageNumber, selectedText: selected.selectedText, selectionPosition: selected.selectionPosition })
  else context()
  // Native multi-page selection must survive auto-scroll across mixed page sizes.
  if (value === previous && mode.value === 'continuous' && window.getSelection()?.isCollapsed === false) return
  fit()
})
watch([current, mode, scale, () => active.value?.zoomMode], () => { if (ready.value && pdf.value && loadedDocumentId === String(route.params.documentId)) progress.value?.stage(readingState()) })
async function selectionChanged() {
  const token = generation, revision = ++selectionRevision, document = pdf.value, root = viewport.value
  if (!document || !root) return
  const selection = await readSelection(document, root).catch(() => ({ selectedText: '', selectionPosition: null }))
  if (token !== generation || revision !== selectionRevision || leaving) return
  const old = readerContext.value
  const pageNumber = selection.selectionPosition?.[0]?.pageNumber || current.value
  if (old?.selectedText === selection.selectedText && old?.pageNumber === pageNumber && JSON.stringify(old.selectionPosition) === JSON.stringify(selection.selectionPosition)) return
  publishContext('selection-change', { documentId: String(route.params.documentId), pageNumber, ...selection })
}
async function resolveProgress(local: boolean) {
  try {
    const value = await progress.value?.resolve(local)
    if (value && active.value) { active.value.zoomMode = value.zoomMode; active.value.zoom = value.zoom || 1; active.value.mode = value.viewMode; jump(value.pageNumber || 1); fit(); await nextTick(); progress.value?.stage(readingState()); await progress.value?.flush() }
  } catch { notice.value = '无法读取最新阅读记录，请稍后重试'; }
}
function pending(name: string) { notice.value = `${name}功能开发中，本阶段不会创建或保存批注数据。` }
watch(group, value => { if (value === '阅读') notice.value = '' })
function openRight(name: string) { rightPanel.value = name; rightOpen.value = true }
async function load(full = false) {
  const token = ++generation, id = String(route.params.documentId)
  suppressScroll = false; layoutRevision++; cancelAnimationFrame(layoutFrame)
  group.value = '阅读'
  metadataRequest?.abort(); metadataRequest = new AbortController()
  const signal = metadataRequest.signal
  const old = resource; resource = undefined
  progress.value?.dispose(); progress.value = createProgress(id); const saving = progress.value
  ready.value = false; loadedDocumentId = ''; navigation = undefined; fitRevision++; selectionRevision++
  sizes.value = []; outline.value = []; outlineError.value = ''; matches.value = []; selectedMatch.value = ''
  pdf.value = undefined; count.value = 0; loading.value = true; failure.value = ''; notice.value = ''
  window.getSelection()?.removeAllRanges()
  context('document-change')
  await nextTick() // Unmount/cancel page render tasks before document destruction.
  await old?.destroy().catch(() => {})
  if (leaving || token !== generation) return
  const tab = openReaderTab(id)
  let owned: ReturnType<typeof createPdfTask> | undefined
  try {
    const doc = await api<DocumentDTO>(`/documents/${encodeURIComponent(id)}`, { signal })
    const saved = await saving.load(signal)
    if (token !== generation || leaving) return
    tab.title = doc.title
    owned = createPdfTask(contentUrl(id), full); resource = owned
    const loaded = await owned.promise
    if (token !== generation || leaving) { await owned.destroy(); return }
    const dimensions: { width: number; height: number }[] = []
    for (let start = 1; start <= loaded.numPages; start += 2) {
      const batch = await Promise.all(Array.from({ length: Math.min(2, loaded.numPages - start + 1) }, async (_, offset) => { const page = await loaded.getPage(start + offset); const v = page.getViewport({ scale: 1 }); return { width: v.width, height: v.height } }))
      if (token !== generation || leaving) return
      dimensions.push(...batch)
    }
    sizes.value = dimensions
    count.value = loaded.numPages; tab.page = Math.min(Math.max(1, saved.pageNumber || 1), loaded.numPages)
    tab.mode = saved.viewMode; tab.zoom = clampZoom(saved.zoom || 1); tab.zoomMode = saved.zoomMode
    zoomInput.value = String(Math.round(tab.zoom * 10000) / 100)
    pageInput.value = String(tab.page); loadedDocumentId = id; pdf.value = loaded; loading.value = false
    void loaded.getOutline().then(value => { if (token === generation) outline.value = (value || []) as OutlineNode[] }).catch(() => { if (token === generation) outlineError.value = '无法读取 PDF 大纲' })
    await nextTick()
    if (token !== generation || leaving) return
    fit(); await nextTick(); jump(tab.page); context('document-change')
  } catch (error) {
    if (token !== generation || leaving) { await owned?.destroy().catch(() => {}); return }
    if (pdfStatus(error) === 416 && !full) { fullFallback = true; void load(true); return }
    await fail(error)
  }
}
async function fail(error: unknown) {
  if (pdfStatus(error) === 416 && !fullFallback) { fullFallback = true; void load(true); return }
  failure.value = pdfError(error); loading.value = false; pdf.value = undefined
  if (pdfStatus(error) === 401) window.dispatchEvent(new Event('litera:unauthenticated'))
  const old = resource; resource = undefined
  await nextTick(); await old?.destroy().catch(() => {})
}
function jump(value: number) {
  if (!pdf.value || !active.value) return
  if (!Number.isInteger(value) || value < 1 || value > count.value) { notice.value = `请输入 1–${count.value} 的整数页码`; pageInput.value = String(current.value); return }
  const revision = ++jumpRevision, token = generation
  window.getSelection()?.removeAllRanges()
  navigating = true; active.value.page = value; pageInput.value = String(value)
  void nextTick(() => {
    if (token !== generation || revision !== jumpRevision) return
    if (mode.value === 'continuous') {
      const node = viewport.value?.querySelector<HTMLElement>(`[data-page="${value}"]`)
      if (node) viewport.value!.scrollTop += node.getBoundingClientRect().top - viewport.value!.getBoundingClientRect().top - PAGE_PADDING
    } else viewport.value?.scrollTo(0, 0)
    requestAnimationFrame(() => { if (revision === jumpRevision) navigating = false })
  })
}
let navigation: { page: number; match?: SearchMatch; point?: number[] } | undefined
async function locate() {
  const target = navigation, root = viewport.value
  if (!target || !root) return
  await nextTick()
  if (navigation !== target) return
  const page = root.querySelector<HTMLElement>(`[data-page="${target.page}"]`)
  if (!page || page.dataset.status !== '已渲染') return
  const mark = target.match ? page.querySelector<HTMLElement>(`[data-match="${target.match.id}"]`) : undefined
  const rect = page.getBoundingClientRect(), bounds = root.getBoundingClientRect()
  if (mark) { const r = mark.getBoundingClientRect(); root.scrollTop += r.top - bounds.top - root.clientHeight / 3; root.scrollLeft += r.left - bounds.left - root.clientWidth / 3 }
  else if (target.point) { root.scrollTop += rect.top + target.point[1]! - bounds.top - PAGE_PADDING; root.scrollLeft += rect.left + target.point[0]! - bounds.left - PAGE_PADDING }
  navigation = undefined
}
async function navigateMatch(match: SearchMatch) {
  selectedMatch.value = match.id; jump(match.pageNumber); navigation = { page: match.pageNumber, match }; await nextTick(); await locate()
}
async function navigateOutline(item: OutlineNode) {
  const token = generation, document = pdf.value
  if (!document) return
  try {
    if (item.url || !item.dest) throw new Error()
    const destination = typeof item.dest === 'string' ? await document.getDestination(item.dest) : item.dest
    if (!destination || destination.length < 2) throw new Error()
    const type = destination[1]?.name
    if (!['XYZ','Fit','FitB','FitH','FitBH','FitV','FitBV','FitR'].includes(type)) throw new Error()
    if (destination.slice(2).some(value => value !== null && (typeof value !== 'number' || !Number.isFinite(value)))) throw new Error()
    if (type === 'FitR' && (destination.length !== 6 || destination.slice(2).some(value => value === null) || destination[4] <= destination[2] || destination[5] <= destination[3])) throw new Error()
    const number = typeof destination[0] === 'number' ? destination[0] + 1 : await document.getPageIndex(destination[0]) + 1
    if (!Number.isInteger(number) || number < 1 || number > document.numPages) throw new Error()
    const page = await document.getPage(number)
    if (token !== generation) return
    jump(number); await nextTick(); fit(); await nextTick()
    const v = page.getViewport({ scale: scale.value })
    let point = [0, 0]
    if (type === 'XYZ' || type === 'FitH' || type === 'FitBH' || type === 'FitV' || type === 'FitBV' || type === 'FitR') {
      const [x0,, , y1] = v.viewBox
      const x = type === 'XYZ' || type === 'FitR' || type === 'FitV' || type === 'FitBV' ? destination[2] ?? x0 : x0
      const y = type === 'XYZ' ? destination[3] ?? y1 : type === 'FitH' || type === 'FitBH' ? destination[2] ?? y1 : type === 'FitR' ? destination[5] ?? y1 : y1
      point = v.convertToViewportPoint(x, y)
    } else if (type !== 'Fit' && type !== 'FitB') throw new Error()
    navigation = { page: number, point }; await locate()
  } catch { if (token === generation) notice.value = '无法跳转：目录目标无效或不是受支持的文内位置' }
}
function step(direction: number) { jump(adjacentPage(current.value, count.value, mode.value, direction)) }
function changeMode(value: unknown) {
  if (!active.value) return
  const restore = anchor(), token = generation
  active.value.mode = value as ViewMode
  active.value.scrollTop = 0
  window.getSelection()?.removeAllRanges()
  jump(current.value)
  void nextTick(async () => { fit(); await nextTick(); if (token === generation) restore() })
}
function scrolled() {
  cancelAnimationFrame(scrollFrame)
  scrollFrame = requestAnimationFrame(() => {
    if (!active.value || !viewport.value || suppressScroll) return
    active.value.scrollTop = viewport.value.scrollTop
    if (mode.value !== 'continuous' || !pdf.value) return
    const bounds = viewport.value.getBoundingClientRect(), center = bounds.top + bounds.height / 2
    let closest = Infinity, found = current.value
    for (const element of viewport.value.querySelectorAll<HTMLElement>('[data-page]')) {
      const rect = element.getBoundingClientRect()
      const distance = center < rect.top ? rect.top - center : center > rect.bottom ? center - rect.bottom : 0
      if (distance < closest) { closest = distance; found = Number(element.dataset.page) }
    }
    active.value.page = found; pageInput.value = String(found)
  })
}
function keydown(event: KeyboardEvent) {
  if (event.target !== viewport.value || mode.value === 'continuous') return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); step(event.key === 'ArrowLeft' ? -1 : 1) }
}
function tabFocus(event: KeyboardEvent) { if (event.key === 'Tab') keyboardFocus.value = true }
function pointerFocus() { keyboardFocus.value = false }
watch(() => route.params.documentId, () => { fullFallback = false; void load() }, { immediate: true })
watch(() => auth.user, (user, previous) => {
  if (!user || user.id !== previous?.id) {
    progress.value?.dispose(true); publishContext('context-cleared'); generation++; metadataRequest?.abort(); clearReaderTabs(); pdf.value = undefined; count.value = 0
    loading.value = false; failure.value = '登录身份已变更，请重新打开文献'
    const old = resource; resource = undefined
    void nextTick(() => { void old?.destroy().catch(() => {}) })
  }
})
function beforeUnload(event: BeforeUnloadEvent) { if (progress.value?.status.dirty) { void progress.value.flush(); event.preventDefault(); event.returnValue = '' } }
onMounted(() => {
  viewport.value?.addEventListener('wheel', wheel, { passive: false })
  document.addEventListener('selectionchange', selectionChanged); window.addEventListener('beforeunload', beforeUnload)
  document.addEventListener('keydown', tabFocus, true)
  resizeObserver = new ResizeObserver(() => { const revision = ++fitRevision; requestAnimationFrame(() => { if (revision === fitRevision && !leaving) fit() }) }); if (viewport.value) resizeObserver.observe(viewport.value)
})
onBeforeUnmount(() => {
  leaving = true; generation++; metadataRequest?.abort(); cancelAnimationFrame(scrollFrame); cancelAnimationFrame(layoutFrame)
  window.getSelection()?.removeAllRanges()
  progress.value?.dispose(); publishContext('context-cleared'); resizeObserver?.disconnect(); viewport.value?.removeEventListener('wheel', wheel)
  document.removeEventListener('selectionchange', selectionChanged); window.removeEventListener('beforeunload', beforeUnload)
  document.removeEventListener('keydown', tabFocus, true)
  const old = resource; resource = undefined
  void nextTick(() => { void old?.destroy().catch(() => {}) })
})
</script>
<template>
  <main class="reader-workspace" :style="{ '--reader-page-padding': PAGE_PADDING + 'px', '--reader-page-gap': PAGE_GAP + 'px' }">
    <header class="reader-brandbar"><Brand /><span class="reader-caption">PDF 阅读器</span><nav><router-link to="/library">返回文献库</router-link><router-link to="/profile">{{ auth.user?.displayName }}</router-link></nav></header>
    <WorkspaceTabs />
    <div class="reader-main-toolbar" aria-label="阅读工具栏">
      <button :aria-label="leftOpen ? '收起文献导航' : '展开文献导航'" :aria-expanded="leftOpen" @click="leftOpen = !leftOpen"><component :is="leftOpen ? Fold : Expand" /></button>
      <div class="reader-paging"><button aria-label="上一页" :disabled="!pdf || current === 1" @click="step(-1)"><ArrowLeft /></button>
        <form @submit.prevent="jump(Number(pageInput))"><input v-model="pageInput" aria-label="当前页码" inputmode="numeric" :disabled="!pdf"><span>/ {{ count || '—' }}</span></form>
        <button aria-label="下一页" :disabled="!pdf || (mode === 'spread' ? pageGroup(current, count, mode).at(-1) === count : current === count)" @click="step(1)"><ArrowRight /></button></div>
      <el-select :model-value="mode" aria-label="阅读视图" class="reader-view-select" @update:model-value="changeMode"><el-option label="单页连续滚动" value="continuous" /><el-option label="单页切换" value="single" /><el-option label="双页并排" value="spread" /></el-select>
      <div class="reader-zoom"><button aria-label="缩小" :disabled="!pdf || scale <= .5" @click="zoom(scale - .25)">−</button><form @submit.prevent="manualZoom"><input v-model="zoomInput" aria-label="缩放比例" :disabled="!pdf" inputmode="decimal"><span>%</span></form><button aria-label="放大" :disabled="!pdf || scale >= 5" @click="zoom(scale + .25)">＋</button>
        <el-dropdown trigger="click" @command="(value: string) => value.startsWith('fit') ? fit(value as ZoomMode) : zoom(Number(value))"><button aria-label="缩放预设" :disabled="!pdf"><ArrowDown class="reader-chevron" aria-hidden="true" /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fit-width">适应宽度</el-dropdown-item><el-dropdown-item command="fit-height">适应高度</el-dropdown-item><el-dropdown-item v-for="value in [50,75,100,125,150,200,300,400,500]" :key="value" :command="String(value / 100)">{{ value }}%</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
      </div>
      <div class="reader-groups" aria-label="工具分组"><button v-for="name in ['阅读','批注','形状','插入']" :key="name" :aria-pressed="group === name" :class="{ selected: group === name }" @click="group = name">{{ name }}</button></div>
      <div class="reader-actions">
        <el-tooltip content="搜索文献" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="搜索文献" @click="openRight('搜索')"><Search /></button></el-tooltip>
        <el-tooltip content="批注列表" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="批注列表" @click="openRight('批注列表')"><ChatLineSquare /></button></el-tooltip>
        <el-tooltip v-if="pdf" content="下载原始 PDF" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><a :href="contentUrl(String(route.params.documentId), true)" aria-label="下载原始 PDF"><Download /></a></el-tooltip>
        <el-tooltip content="导出功能开发中" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="导出功能开发中" @click="pending('导出')"><MoreFilled /></button></el-tooltip>
      </div>
    </div>
    <div v-if="group !== '阅读'" class="reader-secondary" :aria-label="`${group}工具栏`"><button v-for="tool in activeTools" :key="tool[0]" :aria-label="`${tool[0]}（功能开发中）`" aria-disabled="true" @click="pending(tool[0])"><component :is="tool[1]" /><span>{{ tool[0] }}</span></button>
      <span class="reader-toolbar-rule" /><button v-for="color in ['#F5D547','#9B0000','#47A58E','#6395CF']" :key="color" class="reader-color" :style="{ '--swatch': color }" :aria-label="`颜色 ${color}（功能开发中）`" aria-disabled="true" @click="pending('颜色选择')" />
      <button aria-label="撤销（功能开发中）" aria-disabled="true" @click="pending('撤销')"><RefreshLeft /></button><button aria-label="重做（功能开发中）" aria-disabled="true" @click="pending('重做')"><RefreshRight /></button><button aria-label="橡皮擦（功能开发中）" aria-disabled="true" @click="pending('橡皮擦')"><Delete /></button><span class="reader-stage-hint">工具功能开发中</span>
    </div>
    <div v-if="notice" class="reader-notice" role="status">{{ notice }}<button aria-label="关闭提示" @click="notice = ''">×</button></div>
    <div v-if="pdf && ready && progress?.status.error" class="reader-notice" role="alert">{{ progress.status.error }}<div v-if="progress.status.conflict"><button @click="resolveProgress(false)">载入服务端进度</button><button @click="resolveProgress(true)">保存本地进度</button></div><button v-else :disabled="progress.status.saving" @click="progress.retry">重试阅读记录</button></div>
    <div class="reader-body">
      <ReaderPanel v-model:width="leftWidth" :resizable="true" :open="leftOpen" side="left" label="文献导航" @close="leftOpen = false"><div class="reader-panel-tabs"><button v-for="name in ['缩略图','大纲']" :key="name" :class="{ selected: leftPanel === name }" @click="leftPanel = name">{{ name }}</button></div><template v-if="pdf && leftOpen"><div v-if="leftPanel === '缩略图'" class="pdf-thumbnails"><PdfThumbnail v-for="number in count" :key="`${route.params.documentId}-${number}`" :pdf="pdf" :page-number="number" :current="current" @navigate="jump" /></div><template v-else><p v-if="outlineError || !outline.length" class="reader-panel-placeholder" role="status">{{ outlineError || '此 PDF 没有内置大纲' }}</p><PdfOutline v-else :key="String(route.params.documentId)" :items="outline" @navigate="navigateOutline" /></template></template></ReaderPanel>
      <div ref="viewport" class="pdf-viewport" :class="{ 'keyboard-focus': keyboardFocus }" tabindex="0" aria-label="PDF 阅读区域" :aria-busy="loading" @pointerdown="pointerFocus" @scroll.passive="scrolled" @keydown="keydown">
        <div v-if="loading" class="reader-status" role="status"><span class="reader-spinner" /><h1>正在加载 PDF</h1><p>正在读取受保护的文献内容…</p></div>
        <div v-else-if="failure" class="reader-status" role="alert"><Document /><h1>无法打开文献</h1><p>{{ failure }}</p><p v-if="progress?.status.dirty">本地未同步阅读设置已保留，恢复文献后可处理。</p><div><el-button @click="fullFallback = false; load()">重试加载</el-button><el-button @click="router.push('/library')">返回文献库</el-button></div></div>
        <div v-else-if="pdf && viewport" class="pdf-pages" :class="mode" :key="String(route.params.documentId)">
          <PdfPage v-for="number in pages" :key="`${String(route.params.documentId)}-${mode}-${number}`" :pdf="pdf" :page-number="number" :root="viewport" :scale="scale" :size="sizes[number - 1]!" :matches="matchesByPage.get(number) || []" :selected="selectedMatch" @ready="pageReady" @failure="fail" />
        </div>
      </div>
      <ReaderPanel :open="rightOpen" side="right" :label="rightPanel" @close="rightOpen = false"><PdfSearch v-if="pdf" v-show="rightPanel === '搜索'" :key="String(route.params.documentId)" :pdf="pdf" :selected="selectedMatch" @matches="matches = $event; selectedMatch = ''" @navigate="navigateMatch" /><p v-if="rightPanel !== '搜索'" class="reader-panel-placeholder">批注列表功能将在 P3-B1 提供。</p></ReaderPanel>
    </div>
  </main>
</template>
