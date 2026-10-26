<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import 'pdfjs-dist/web/pdf_viewer.css'
import type { SearchMatch } from '../reader/search'
import { validateSourceTextRanges, type SourceHighlightRequest, type SourceHighlightResult } from '../reader/sourceHighlight'
import PdfAnnotations from './PdfAnnotations.vue'
import PdfNativeComments from './PdfNativeComments.vue'
import PdfDrawingObjects from './PdfDrawingObjects.vue'
import { drawingTypes } from '../reader/objectGeometry'
import type { ReaderAsset } from '../reader/assets'
import type { AnnotationDTO, AnnotationType } from '../reader/annotations'
const props = defineProps<{ pdf: PDFDocumentProxy; documentId: string; drawingColor: string; drawingWidth: number; drawingOpacity: number; placement?: ReaderAsset | null; pageNumber: number; root: HTMLElement; scale: number; size: { width: number; height: number }; matches: SearchMatch[]; selected: string; sourceHighlight?: SourceHighlightRequest | null; annotations?: AnnotationDTO[]; selectedAnnotation?: string; annotationTool?: AnnotationType | 'erase' | ''; annotationEnabled?: boolean; annotationGroup?: string; annotationEditor?: AnnotationDTO | null; editorLocked?: boolean; editorBusy?: boolean; editingActive?: boolean }>()
const emit = defineEmits<{ ready: [number]; failure: [unknown]; sourceLocate: [SourceHighlightResult]; annotationSelect: [AnnotationDTO]; annotationPlace: [number, number, number]; annotationMove: [string, AnnotationDTO['geometry']]; annotationEdit: [AnnotationDTO]; annotationDraft: [AnnotationDTO]; annotationSave: []; annotationCancel: []; annotationDraw: [AnnotationType,AnnotationDTO['geometry']]; annotationWarning: [string]; annotationReplaceAsset: [] }>()
const host = ref<HTMLElement>(), canvas = ref<HTMLCanvasElement>(), text = ref<HTMLElement>()
const dimensions = computed(() => ({ width: props.size.width * props.scale, height: props.size.height * props.scale }))
const highlights = ref<{ id: string; x: number; y: number; width: number; height: number }[]>([])
const sourceMarks = ref<{ x: number; y: number; width: number; height: number }[]>([])
const status = ref('等待渲染')
const userUnit = ref(1)
const resolutionLimited = ref(false)
const renderedPage=shallowRef<PDFPageProxy>()
let observer: IntersectionObserver | undefined, page: PDFPageProxy | undefined
let renderTask: RenderTask | undefined, layer: TextLayer | undefined
let generation = 0, disposed = false, wanted = false, running = false
let staging: HTMLCanvasElement | undefined
let zoomTimer: ReturnType<typeof setTimeout> | undefined
let pointerStart = { x: 0, y: 0 }
function startTextSelection(event: PointerEvent) {
  // A new drag inside an old selection otherwise starts native HTML text DnD,
  // leaving the previous Range intact. Keep Shift extension and copy untouched.
  if (event.button === 0 && !event.shiftKey && !window.getSelection()?.isCollapsed) window.getSelection()?.removeAllRanges()
}
function selectTextMark(event: MouseEvent) {
  // Let the browser finish native character selection first. A click-through
  // hit test selects an annotation only when the gesture was not a text drag.
  if (Math.hypot(event.clientX-pointerStart.x,event.clientY-pointerStart.y)>3 || !window.getSelection()?.isCollapsed) return
  if (props.annotationTool && props.annotationTool !== 'erase') return
  if (!props.annotationEnabled) {
    for(const el of [...host.value!.querySelectorAll<SVGGraphicsElement>('[data-drawing]')].reverse()) { const r=el.getBoundingClientRect(); if(event.clientX>=r.left && event.clientX<=r.right && event.clientY>=r.top && event.clientY<=r.bottom) { const a=props.annotations?.find(a=>a.id===el.dataset.drawing);if(a){emit('annotationSelect',a);return} } }
  }
  for (const polygon of [...host.value!.querySelectorAll<SVGPolygonElement>('.annotation-text-mark polygon')].reverse()) {
    const r = polygon.getBoundingClientRect()
    if (event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) continue
    const item = props.annotations?.find(a => a.id === polygon.parentElement!.getAttribute('data-annotation'))
    if (item) { emit('annotationSelect',item); return }
  }
}
function markMatches() {
  if (!layer || status.value !== '已渲染' || !host.value) { highlights.value = []; return }
  const bounds = host.value.getBoundingClientRect(), marks: typeof highlights.value = []
  for (const match of props.matches) for (const part of match.parts) {
    const node = layer.textDivs[part.item]?.firstChild
    if (!node || node.nodeType !== Node.TEXT_NODE) continue
    const range = document.createRange(); range.setStart(node, Math.min(part.start, node.textContent!.length)); range.setEnd(node, Math.min(part.end, node.textContent!.length))
    for (const rect of range.getClientRects()) marks.push({ id: match.id, x: rect.left - bounds.left, y: rect.top - bounds.top, width: rect.width, height: rect.height })
  }
  highlights.value = marks
}

async function updateSourceHighlight() {
  const request = props.sourceHighlight
  if (!request || request.position.pageNumber !== props.pageNumber) { sourceMarks.value = []; return }
  if (!layer || status.value !== '已渲染' || !host.value) return
  const spans = layer.textDivs
  const values: string[] = [], breaks: boolean[] = []
  for (const span of spans) {
    const node = span.firstChild
    values.push(node?.nodeType === Node.TEXT_NODE ? node.textContent || '' : '')
    breaks.push(span.nextSibling?.nodeName === 'BR')
  }
  const checked = validateSourceTextRanges(request.position, values, breaks)
  if (!checked.ok) {
    sourceMarks.value = []
    emit('sourceLocate', { token: request.token, pageNumber: props.pageNumber, status: 'page-only', reason: checked.reason })
    return
  }
  const bounds = host.value.getBoundingClientRect(), marks: typeof sourceMarks.value = []
  for (const part of checked.parts) {
    const node = spans[part.item]?.firstChild
    if (!node || node.nodeType !== Node.TEXT_NODE) continue
    const range = document.createRange()
    range.setStart(node, part.start); range.setEnd(node, part.end)
    for (const rect of range.getClientRects()) if (rect.width > 0 && rect.height > 0) marks.push({ x: rect.left - bounds.left, y: rect.top - bounds.top, width: rect.width, height: rect.height })
  }
  if (!marks.length) {
    sourceMarks.value = []
    emit('sourceLocate', { token: request.token, pageNumber: props.pageNumber, status: 'page-only', reason: '当前文字层未产生可见的原文位置。' })
    return
  }
  sourceMarks.value = marks
  await nextTick()
  if (props.sourceHighlight?.token === request.token && status.value === '已渲染') emit('sourceLocate', { token: request.token, pageNumber: props.pageNumber, status: 'exact' })
}

function release() {
  renderedPage.value=undefined
  generation++
  renderTask?.cancel(); layer?.cancel()
  text.value?.replaceChildren()
  highlights.value = []
  sourceMarks.value = []
  if (canvas.value) { canvas.value.width = 0; canvas.value.height = 0 }
  status.value = '等待渲染'
}
async function render() {
  if (running || disposed || !wanted || status.value === '已渲染') return
  running = true
  const current = ++generation
  let stagedText: HTMLDivElement | undefined
  try {
    page = await props.pdf.getPage(props.pageNumber)
    if (disposed || current !== generation) return
    userUnit.value = page.userUnit
    const viewport = page.getViewport({ scale: props.scale })
    const target = canvas.value!, container = text.value!
    // Logical scale is shared by every layer. DPR affects only backing pixels.
    const dpr = Math.min(window.devicePixelRatio || 1, 2,
      8192 / viewport.width, 8192 / viewport.height,
      Math.sqrt(16_000_000 / (viewport.width * viewport.height)))
    resolutionLimited.value = dpr + .001 < Math.min(window.devicePixelRatio || 1, 2)
    staging = document.createElement('canvas')
    staging.width = Math.ceil(viewport.width * dpr); staging.height = Math.ceil(viewport.height * dpr)
    status.value = '正在渲染'
    renderTask = page.render({ canvas: staging, viewport,
      transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0] })
    await renderTask.promise
    if (disposed || current !== generation) return
    // Commit a complete frame, never a partially painted image or a different page.
    stagedText = document.createElement('div'); stagedText.className = 'textLayer'
    stagedText.style.visibility = 'hidden'; host.value!.append(stagedText)
    layer = new TextLayer({ textContentSource: page.streamTextContent(), container: stagedText, viewport })
    await layer.render()
    if (disposed || current !== generation) { stagedText.remove(); return }
    layer.textDivs.forEach((span, item) => { span.dataset.textItem = String(item) })
    target.width = staging.width; target.height = staging.height
    target.getContext('2d')!.drawImage(staging, 0, 0)
    container.replaceChildren(...stagedText.childNodes); container.style.cssText = stagedText.style.cssText; container.style.visibility = ''
    // TextLayer rotation is an attribute consumed by PDF.js CSS, not an inline style.
    // Preserve it when committing the staged layer, including intrinsic PDF Rotate.
    container.setAttribute('data-main-rotation', stagedText.getAttribute('data-main-rotation') || '0')
    stagedText.remove()
    renderedPage.value=page
    status.value = '已渲染'; await nextTick(); markMatches(); await updateSourceHighlight(); emit('ready', props.pageNumber)
  } catch (error) {
    if (!disposed && current === generation) { status.value = '渲染失败'; emit('failure', error) }
  } finally {
    stagedText?.remove()
    if (staging) { staging.width = 0; staging.height = 0; staging = undefined }
    running = false
    if (disposed || !wanted) { page?.cleanup(); page = undefined }
    else if (current !== generation && !zoomTimer) void render()
  }
}
onMounted(() => {
  observer = new IntersectionObserver(entries => {
    const visible = entries[0]!.isIntersecting
    if (visible === wanted) return
    wanted = visible
    if (wanted) void render()
    else { release(); if (!running) { page?.cleanup(); page = undefined } }
  }, { root: props.root, rootMargin: '500px 0px' })
  observer.observe(host.value!)
})
watch(() => props.scale, () => {
  renderedPage.value=undefined
  generation++; renderTask?.cancel(); layer?.cancel(); highlights.value = []; sourceMarks.value = []; status.value = '等待渲染'
  if (!wanted && canvas.value) { canvas.value.width = canvas.value.height = 0; text.value?.replaceChildren() }
  clearTimeout(zoomTimer); zoomTimer = setTimeout(() => { zoomTimer = undefined; if (wanted) void render() }, 100)
})
watch(() => [props.matches, props.selected], () => { void nextTick(markMatches) })
watch(() => props.sourceHighlight, () => { void nextTick(updateSourceHighlight) }, { deep: true })
onBeforeUnmount(() => { disposed = true; wanted = false; clearTimeout(zoomTimer); observer?.disconnect(); release(); if (!running) page?.cleanup() })
</script>
<template>
  <section ref="host" class="pdf-page" :data-page="pageNumber" :data-status="status"
    :aria-label="`第 ${pageNumber} 页`" :style="{ width: dimensions.width + 'px', height: dimensions.height + 'px', '--scale-factor': scale, '--user-unit': userUnit, '--total-scale-factor': scale * userUnit }" @pointerdown="pointerStart = { x: $event.clientX, y: $event.clientY }" @click="selectTextMark">
    <canvas ref="canvas" width="0" height="0" :aria-label="`PDF 第 ${pageNumber} 页画布`" />
    <span v-if="resolutionLimited && status === '已渲染'" class="pdf-resolution-hint" title="保留当前阅读倍率；画布达到单页像素上限，缩小倍率可恢复设备原生采样。">当前画布已达分辨率上限</span>
    <div class="pdf-source-highlight-layer" aria-hidden="true"><span v-for="(mark, i) in sourceMarks" :key="i" :data-source-highlight-token="sourceHighlight?.token" data-testid="source-highlight" :style="{ left: mark.x + 'px', top: mark.y + 'px', width: mark.width + 'px', height: mark.height + 'px' }" /></div>
    <div ref="text" class="textLayer" :style="{ visibility: status === '已渲染' ? 'visible' : 'hidden' }" @pointerdown="startTextSelection" @dragstart.prevent />
    <div class="pdf-search-layer" aria-hidden="true"><span v-for="(mark, i) in highlights" :key="i" :data-match="mark.id" :class="{ current: mark.id === selected }" :style="{ left: mark.x + 'px', top: mark.y + 'px', width: mark.width + 'px', height: mark.height + 'px' }" /></div>
    <PdfNativeComments v-if="renderedPage" :page="renderedPage" :scale="scale" :enabled="!annotationTool && !editingActive" />
    <PdfAnnotations :pdf="pdf" :page-number="pageNumber" :scale="scale" :items="(annotations || []).filter(a=>!drawingTypes.includes(a.type))" :editor="annotationEditor?.type==='freeText' ? annotationEditor : null" :editor-locked="editorLocked" :editor-busy="editorBusy" :editing-active="editingActive" :selected="selectedAnnotation || ''" :tool="annotationTool || ''" :enabled="annotationGroup==='批注'" @select="emit('annotationSelect',$event)" @edit="emit('annotationEdit',$event)" @draft="emit('annotationDraft',$event)" @save="emit('annotationSave')" @cancel="emit('annotationCancel')" @place="(p,x,y) => emit('annotationPlace',p,x,y)" @move="(id,g) => emit('annotationMove',id,g)" />
    <PdfDrawingObjects :pdf="pdf" :document-id="documentId" :page-number="pageNumber" :scale="scale" :items="annotations || []" :editor="annotationEditor" :selected="selectedAnnotation || ''" :tool="annotationTool || ''" :enabled="annotationEnabled || false" :group="annotationGroup || '阅读'" :locked="editorLocked" :busy="editorBusy" :editing-active="editingActive" :color="drawingColor" :line-width="drawingWidth" :opacity="drawingOpacity" :placement="placement" @select="emit('annotationSelect',$event)" @edit="emit('annotationEdit',$event)" @draft="emit('annotationDraft',$event)" @move="(id,g)=>emit('annotationMove',id,g)" @draw="(type,g)=>emit('annotationDraw',type,g)" @warning="emit('annotationWarning',$event)" @replace-asset="emit('annotationReplaceAsset')" @save="emit('annotationSave')" @cancel="emit('annotationCancel')" />
    <span v-if="status === '正在渲染'" class="pdf-page-loading" role="status" :aria-label="`正在加载第 ${pageNumber} 页`" />
  </section>
</template>
<style scoped>
.pdf-resolution-hint { position:absolute; top:6px; left:6px; z-index:1; padding:3px 6px; border-radius:4px; background:var(--litera-page); color:var(--litera-muted); font-size:11px; pointer-events:none }
.pdf-source-highlight-layer { position:absolute; inset:0; z-index:1; pointer-events:none }
.pdf-source-highlight-layer span { position:absolute; box-sizing:border-box; border-radius:2px; background:#ffb74d66; outline:1px solid #e27700b8; box-shadow:0 0 0 1px #fff5 inset }
</style>
