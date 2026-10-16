<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import 'pdfjs-dist/web/pdf_viewer.css'
import type { SearchMatch } from '../reader/search'
import PdfAnnotations from './PdfAnnotations.vue'
import type { AnnotationDTO, AnnotationType } from '../reader/annotations'
const props = defineProps<{ pdf: PDFDocumentProxy; pageNumber: number; root: HTMLElement; scale: number; size: { width: number; height: number }; matches: SearchMatch[]; selected: string; annotations?: AnnotationDTO[]; selectedAnnotation?: string; annotationTool?: AnnotationType | 'erase' | ''; annotationEnabled?: boolean; annotationEditor?: AnnotationDTO | null; editorLocked?: boolean; editorBusy?: boolean; editingActive?: boolean }>()
const emit = defineEmits<{ ready: [number]; failure: [unknown]; annotationSelect: [AnnotationDTO]; annotationPlace: [number, number, number]; annotationMove: [string, AnnotationDTO['geometry']]; annotationEdit: [AnnotationDTO]; annotationDraft: [AnnotationDTO]; annotationSave: []; annotationCancel: [] }>()
const host = ref<HTMLElement>(), canvas = ref<HTMLCanvasElement>(), text = ref<HTMLElement>()
const dimensions = computed(() => ({ width: props.size.width * props.scale, height: props.size.height * props.scale }))
const highlights = ref<{ id: string; x: number; y: number; width: number; height: number }[]>([])
const status = ref('等待渲染')
const userUnit = ref(1)
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

function release() {
  generation++
  renderTask?.cancel(); layer?.cancel()
  text.value?.replaceChildren()
  highlights.value = []
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
    status.value = '已渲染'; await nextTick(); markMatches(); emit('ready', props.pageNumber)
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
  generation++; renderTask?.cancel(); layer?.cancel(); highlights.value = []; status.value = '等待渲染'
  if (!wanted && canvas.value) { canvas.value.width = canvas.value.height = 0; text.value?.replaceChildren() }
  clearTimeout(zoomTimer); zoomTimer = setTimeout(() => { zoomTimer = undefined; if (wanted) void render() }, 100)
})
watch(() => [props.matches, props.selected], () => { void nextTick(markMatches) })
onBeforeUnmount(() => { disposed = true; wanted = false; clearTimeout(zoomTimer); observer?.disconnect(); release(); if (!running) page?.cleanup() })
</script>
<template>
  <section ref="host" class="pdf-page" :data-page="pageNumber" :data-status="status"
    :aria-label="`第 ${pageNumber} 页`" :style="{ width: dimensions.width + 'px', height: dimensions.height + 'px', '--scale-factor': scale, '--user-unit': userUnit, '--total-scale-factor': scale * userUnit }" @pointerdown="pointerStart = { x: $event.clientX, y: $event.clientY }" @click="selectTextMark">
    <canvas ref="canvas" width="0" height="0" :aria-label="`PDF 第 ${pageNumber} 页画布`" />
    <div ref="text" class="textLayer" :style="{ visibility: status === '已渲染' ? 'visible' : 'hidden' }" @pointerdown="startTextSelection" @dragstart.prevent />
    <div class="pdf-search-layer" aria-hidden="true"><span v-for="(mark, i) in highlights" :key="i" :data-match="mark.id" :class="{ current: mark.id === selected }" :style="{ left: mark.x + 'px', top: mark.y + 'px', width: mark.width + 'px', height: mark.height + 'px' }" /></div>
    <PdfAnnotations :pdf="pdf" :page-number="pageNumber" :scale="scale" :items="annotations || []" :editor="annotationEditor" :editor-locked="editorLocked" :editor-busy="editorBusy" :editing-active="editingActive" :selected="selectedAnnotation || ''" :tool="annotationTool || ''" :enabled="annotationEnabled || false" @select="emit('annotationSelect',$event)" @edit="emit('annotationEdit',$event)" @draft="emit('annotationDraft',$event)" @save="emit('annotationSave')" @cancel="emit('annotationCancel')" @place="(p,x,y) => emit('annotationPlace',p,x,y)" @move="(id,g) => emit('annotationMove',id,g)" />
    <span v-if="status === '正在渲染'" class="pdf-page-loading" role="status" :aria-label="`正在加载第 ${pageNumber} 页`" />
  </section>
</template>
