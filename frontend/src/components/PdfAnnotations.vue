<script setup lang="ts">
import { computed, shallowRef, watch, onBeforeUnmount, nextTick, ref } from 'vue'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import { normalizedToViewport, viewportToNormalized } from '../reader/state'
import type { AnnotationDTO, AnnotationType } from '../reader/annotations'
import type { NormalizedRect } from '../reader/context'
import { smoothWave, textStroke, textMarkLines } from '../reader/annotationGeometry'
import { boxHandles, resizeBox, type BoxHandle } from '../reader/boxGeometry'
import AnnotationProperties from './AnnotationProperties.vue'
import AnnotationTextContent from './AnnotationTextContent.vue'
import { showComment,leaveComment } from '../reader/commentPopup'
const props = defineProps<{ pdf: PDFDocumentProxy; pageNumber: number; scale: number; items: AnnotationDTO[]; selected: string; tool: AnnotationType | 'erase' | ''; enabled: boolean; editor?: AnnotationDTO | null; editorLocked?: boolean; editorBusy?: boolean; editingActive?: boolean }>()
const emit = defineEmits<{ select: [AnnotationDTO]; edit: [AnnotationDTO]; draft: [AnnotationDTO]; save: []; cancel: []; place: [number, number, number]; move: [string, AnnotationDTO['geometry']] }>()
const page = shallowRef<PDFPageProxy>()
watch(() => [props.pdf, props.pageNumber] as const, async ([pdf, number]) => { const p = await pdf.getPage(number); if (props.pdf === pdf && props.pageNumber === number) page.value = p }, { immediate: true })
const viewport = computed(() => page.value?.getViewport({ scale: props.scale }))
const placing = computed(() => props.enabled && ['comment', 'freeText'].includes(props.tool))
function point(x: number, y: number) { return viewport.value ? normalizedToViewport(viewport.value, x, y) : [0, 0] }
function markerTransform(x: number, y: number) {
  const p = point(x,y)
  return `translate(${p.join(' ')}) scale(${p[0]! > viewport.value!.width-25 ? -1 : 1} ${p[1]! < 23 ? -1 : 1})`
}
function polygon(r: NormalizedRect) { return [[r.x,r.y],[r.x+r.width,r.y],[r.x+r.width,r.y+r.height],[r.x,r.y+r.height]].map(([x,y]) => point(x!, y!).join(',')).join(' ') }
function stroke(r: NormalizedRect, item: AnnotationDTO) { return textStroke(r, (page.value!.view[3]!-page.value!.view[1]!), (item.style.lineWidth || 1)/page.value!.userUnit, item.type==='strikeout') }
function line(r: NormalizedRect, item: AnnotationDTO, body = r) { const y = stroke(body,item).y; return [point(r.x,y), point(r.x+r.width,y)] }
function wave(r: NormalizedRect, item: AnnotationDTO, body = r) {
  const [a,b] = line(r,item,body), unit = props.scale * page.value!.userUnit
  return smoothWave(a!,b!,stroke(body,item).amplitude*unit,Math.max(3, body.height*(page.value!.view[3]!-page.value!.view[1]!)*.32)*unit)
}
const preview = shallowRef<{ id: string; geometry: AnnotationDTO['geometry'] }>()
let cancelDrag: (() => void) | undefined
let skipClick = false
let readingClickTimer: ReturnType<typeof setTimeout> | undefined
function select(item: AnnotationDTO, event?: MouseEvent) {
  if (skipClick) return
  if (item.type==='freeText' && !props.enabled && event) {
    // Opening the panel can reflow the PDF between the two native clicks.
    clearTimeout(readingClickTimer)
    if (event.detail===1) readingClickTimer=setTimeout(()=>emit('select',item),350)
    return
  }
  emit('select',item)
}
function edit(item: AnnotationDTO) { clearTimeout(readingClickTimer); if(item.type==='freeText') emit('edit',item) }
const visibleItems = computed(() => {
  const items=props.editor && !props.items.some(a=>a.id===props.editor!.id) ? [...props.items,props.editor] : props.items
  return items.map(a => { const item=props.editor?.id===a.id ? props.editor : a; return preview.value?.id===a.id ? {...item,geometry:preview.value.geometry} : item })
})
watch(() => [props.pdf,props.pageNumber,props.scale,props.enabled,props.tool], () => { cancelDrag?.(); clearTimeout(readingClickTimer) })
onBeforeUnmount(() => { cancelDrag?.(); clearTimeout(readingClickTimer) })
const marks = computed(() => visibleItems.value.flatMap(item => {
  const g = item.geometry
  const rects = g.kind === 'text' ? g.positions.filter(p => p.pageNumber === props.pageNumber).flatMap(p => p.rects) : g.kind === 'box' && g.pageNumber === props.pageNumber ? [g.rect] : []
  return (g.kind === 'text' && page.value ? textMarkLines(rects, page.value.view[2]!-page.value.view[0]!, page.value.view[3]!-page.value.view[1]!) : rects.map(rect=>({rect,body:rect}))).map(({rect,body}, index) => ({ item, rect, body, index }))
}))
const anchors = computed(() => visibleItems.value.filter(a => a.geometry.kind === 'anchor' && a.pageNumber === props.pageNumber))
function boxTransform(r: NormalizedRect) {
  const a = point(r.x,r.y), b = point(r.x+r.width,r.y), c = point(r.x,r.y+r.height)
  const w = boxWidth(r), h = boxHeight(r)
  return `matrix(${(b[0]!-a[0]!)/w} ${(b[1]!-a[1]!)/w} ${(c[0]!-a[0]!)/h} ${(c[1]!-a[1]!)/h} ${a[0]} ${a[1]})`
}
function boxWidth(r: NormalizedRect) { return r.width*(page.value!.view[2]!-page.value!.view[0]!) }
function boxHeight(r: NormalizedRect) { return r.height*(page.value!.view[3]!-page.value!.view[1]!) }
function local(event: PointerEvent | MouseEvent) {
  const svg = (event.currentTarget as SVGElement).closest('svg')!, rect = svg.getBoundingClientRect()
  return viewportToNormalized(viewport.value!, (event.clientX - rect.left)*viewport.value!.width/rect.width, (event.clientY - rect.top)*viewport.value!.height/rect.height)
}
function place(event: MouseEvent) { if (placing.value && viewport.value) { event.stopPropagation(); const p = local(event); emit('place', props.pageNumber, p.x, p.y) } }
function drag(event: PointerEvent, item: AnnotationDTO, resize?: BoxHandle) {
  skipClick = false
  if (event.button!==0 || !props.enabled || props.tool === 'erase' || item.geometry.kind === 'text' || !viewport.value || props.editorLocked || (props.editingActive && props.editor?.id!==item.id)) return
  emit('select',item)
  event.preventDefault(); event.stopPropagation()
  const element = event.currentTarget as SVGElement, start = local(event), original: AnnotationDTO['geometry'] = JSON.parse(JSON.stringify(item.geometry))
  element.closest<HTMLElement>('.pdf-viewport')?.focus({ preventScroll: true })
  element.setPointerCapture(event.pointerId)
  let latest: AnnotationDTO['geometry'] = original
  let moved = false
  function move(e: PointerEvent) {
    // currentTarget belongs to the captured element for each listener.
    const p = local(e), dx = p.x-start.x, dy = p.y-start.y
    if (original.kind === 'anchor') latest = { ...original, x: Math.max(0,Math.min(1,original.x+dx)), y: Math.max(0,Math.min(1,original.y+dy)) }
    else if (original.kind === 'box') {
      const r = original.rect
      latest = { ...original, rect: resize ? resizeBox(r,dx,dy,resize) : { ...r, x: Math.max(0,Math.min(1-r.width,r.x+dx)), y: Math.max(0,Math.min(1-r.height,r.y+dy)) } }
    }
    moved ||= Math.hypot(e.clientX-event.clientX,e.clientY-event.clientY)>3
    if (moved) preview.value = { id:item.id, geometry:latest }
  }
  function cleanup() {
    element.removeEventListener('pointermove',move); element.removeEventListener('pointerup',stop); element.removeEventListener('pointercancel',stop)
    element.removeEventListener('lostpointercapture',cleanup); window.removeEventListener('blur',cleanup)
    document.removeEventListener('keydown',escape,true); document.body.classList.remove('annotation-dragging')
    if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId)
    preview.value=undefined; cancelDrag=undefined
  }
  function stop(e: PointerEvent) {
    const commit = e.type==='pointerup' && moved && JSON.stringify(latest)!==JSON.stringify(original)
    skipClick = moved
    cleanup()
    if (commit) emit('move',item.id,latest)
  }
  function escape(e: KeyboardEvent) { if(e.key==='Escape') { e.preventDefault(); e.stopImmediatePropagation(); skipClick = true; cleanup() } }
  cancelDrag=cleanup; document.addEventListener('keydown',escape,true); document.body.classList.add('annotation-dragging')
  element.addEventListener('lostpointercapture',cleanup); window.addEventListener('blur',cleanup)
  element.addEventListener('pointermove',move); element.addEventListener('pointerup',stop); element.addEventListener('pointercancel',stop)
}
function handlePoint(r: NormalizedRect, handle: BoxHandle) { return point(r.x+(handle.includes('w') ? 0 : handle.includes('e') ? r.width : r.width/2),r.y+(handle.includes('n') ? 0 : handle.includes('s') ? r.height : r.height/2)) }
const editorOnPage = computed(() => props.editor?.geometry.kind==='box' && props.editor.pageNumber===props.pageNumber ? props.editor : null)
const textarea = ref<HTMLTextAreaElement[]>()
watch(() => editorOnPage.value?.id, async id => { if(id) { await nextTick(); textarea.value?.[0]?.focus({preventScroll:true}) } },{immediate:true})
const controlsPosition = computed(() => {
  const item=visibleItems.value.find(a=>a.id===editorOnPage.value?.id), g=item?.geometry
  if (!viewport.value || g?.kind!=='box') return {}
  const corners=[[g.rect.x,g.rect.y],[g.rect.x+g.rect.width,g.rect.y],[g.rect.x,g.rect.y+g.rect.height],[g.rect.x+g.rect.width,g.rect.y+g.rect.height]].map(([x,y])=>point(x!,y!))
  const bottom=Math.max(...corners.map(p=>p[1]!)), top=Math.min(...corners.map(p=>p[1]!))
  return { left: Math.max(4,Math.min(viewport.value.width-300,Math.min(...corners.map(p=>p[0]!))))+'px', top: Math.max(4,bottom+180<viewport.value.height ? bottom+8 : top-180)+'px', maxWidth:Math.max(100,viewport.value.width-8)+'px' }
})
</script>
<template>
  <svg v-if="viewport" class="reader-object-layer annotation-overlay" :class="{ placing }" :width="viewport.width" :height="viewport.height" :viewBox="`0 0 ${viewport.width} ${viewport.height}`" @click.capture="place">
    <g v-for="item in anchors" :key="item.id" tabindex="0" @mouseenter="showComment(item.id,item.content,$event.currentTarget as Element)" @mouseleave="leaveComment(item.id)" @keydown.enter.prevent="showComment(item.id,item.content,$event.currentTarget as Element,true)" class="annotation-hit annotation-anchor" :class="{ 'drag-preview': preview?.id===item.id }" :data-annotation="item.id" :opacity="item.style.opacity ?? 1" :transform="markerTransform((item.geometry as any).x,(item.geometry as any).y)" role="button" :aria-label="`注释 ${item.content}`" @click.stop="showComment(item.id,item.content,$event.currentTarget as Element,true);select(item)" @pointerdown="drag($event,item)"><path d="M 0 0 L 0 -18 Q 0 -21 3 -21 H 20 Q 23 -21 23 -18 V -7 Q 23 -4 20 -4 H 6 Z" :fill="item.color" :stroke="enabled && selected===item.id ? '#9B0000' : '#fff'" stroke-width="1.2" /><path d="M 5 -15 H 18 M 5 -10 H 15" stroke="white" stroke-width="1.4" stroke-linecap="round" /></g>
    <g v-for="mark in marks" :key="`${mark.item.id}-${mark.index}`" :data-annotation="mark.item.id" :opacity="mark.item.type==='highlight' || editor?.id===mark.item.id ? 1 : (mark.item.style.opacity ?? 1)" :class="{ 'annotation-selected': enabled && selected === mark.item.id, 'annotation-text-mark': mark.item.geometry.kind==='text', 'drag-preview': preview?.id===mark.item.id, 'erasable': tool==='erase' }" class="annotation-hit" role="button" :aria-label="`批注 ${mark.item.content || mark.item.selectedText}`" @click.stop="select(mark.item,$event)" @dblclick.stop="edit(mark.item)" @pointerdown="drag($event,mark.item)">
      <polygon :points="polygon(mark.rect)" :fill="mark.item.type === 'highlight' ? mark.item.color : 'transparent'" :fill-opacity="mark.item.type === 'highlight' ? (mark.item.style.opacity ?? .35) : 1" :stroke="enabled && selected === mark.item.id ? '#9B0000' : 'none'" stroke-width="1" />
      <line v-if="['underline','strikeout'].includes(mark.item.type)" :x1="line(mark.rect,mark.item,mark.body)[0]![0]" :y1="line(mark.rect,mark.item,mark.body)[0]![1]" :x2="line(mark.rect,mark.item,mark.body)[1]![0]" :y2="line(mark.rect,mark.item,mark.body)[1]![1]" :stroke="mark.item.color" :stroke-width="stroke(mark.body,mark.item).thickness*scale*page!.userUnit" />
      <path v-if="mark.item.type==='squiggly'" :d="wave(mark.rect,mark.item,mark.body)" stroke-linecap="round" stroke-linejoin="round" fill="none" :stroke="mark.item.color" :stroke-width="stroke(mark.body,mark.item).thickness*scale*page!.userUnit" />
      <g v-if="mark.item.type==='comment' && mark.index===0" tabindex="0" @mouseenter="showComment(mark.item.id,mark.item.content,$event.currentTarget as Element)" @mouseleave="leaveComment(mark.item.id)" @keydown.enter.prevent="showComment(mark.item.id,mark.item.content,$event.currentTarget as Element,true)" class="annotation-comment-icon" :transform="markerTransform(mark.rect.x,mark.rect.y)" @click.stop="showComment(mark.item.id,mark.item.content,$event.currentTarget as Element,true);select(mark.item)"><path d="M 0 0 L 0 -18 Q 0 -21 3 -21 H 20 Q 23 -21 23 -18 V -7 Q 23 -4 20 -4 H 6 Z" :fill="mark.item.color" stroke="white" stroke-width="1.2" /><path d="M 5 -15 H 18 M 5 -10 H 15" stroke="white" stroke-width="1.4" stroke-linecap="round" /></g>
      <foreignObject v-if="mark.item.type==='freeText'" :transform="boxTransform(mark.rect)" :width="boxWidth(mark.rect)" :height="boxHeight(mark.rect)" :style="{overflow:'hidden','--free-text-padding':(3/(scale*page!.userUnit))+'px'}">
        <textarea v-if="editor?.id===mark.item.id" ref="textarea" xmlns="http://www.w3.org/1999/xhtml" class="annotation-free-text free-text-input" aria-label="批注正文" :value="mark.item.content || ''" :readonly="editorLocked" maxlength="20000" :style="{color:mark.item.color,opacity:mark.item.style.opacity ?? 1,fontSize:((mark.item.style.fontSize || 14)/page!.userUnit)+'px',lineHeight:1.25}" @input="emit('draft',{...mark.item,content:($event.target as HTMLTextAreaElement).value})" @pointerdown.stop @click.stop @dblclick.stop @keydown.stop @pointerup.stop />
        <AnnotationTextContent v-else :content="mark.item.content" :color="mark.item.color" :font-size="(mark.item.style.fontSize || 14)/page!.userUnit" />
      </foreignObject>
      <template v-if="mark.item.geometry.kind==='box' && enabled && selected===mark.item.id && !editorLocked">
        <line v-if="editor?.id===mark.item.id" :x1="point(mark.rect.x,mark.rect.y)[0]" :y1="point(mark.rect.x,mark.rect.y)[1]" :x2="point(mark.rect.x+mark.rect.width,mark.rect.y)[0]" :y2="point(mark.rect.x+mark.rect.width,mark.rect.y)[1]" stroke="#9b0000" stroke-opacity="0.35" stroke-width="7" class="free-text-move" aria-label="移动自由文本" @pointerdown.stop="drag($event,mark.item)" />
        <circle v-for="handle in boxHandles" :key="handle" :cx="handlePoint(mark.rect,handle)[0]" :cy="handlePoint(mark.rect,handle)[1]" r="4" fill="white" stroke="#9B0000" class="annotation-resize" :data-handle="handle" :style="{cursor:handle+'-resize'}" @pointerdown.stop="drag($event,mark.item,handle)" />
      </template>
    </g>

  </svg>
  <form v-if="viewport && editorOnPage" class="free-text-controls" :style="controlsPosition" @submit.prevent="editorOnPage.content?.trim() && emit('save')" @pointerdown.stop @click.stop @keydown.stop>
    <AnnotationProperties :item="editorOnPage" :disabled="editorLocked" @change="emit('draft',$event)" />
    <p class="free-text-overflow-hint">内容超出框时可滚动编辑；请增大文本框以完整显示。</p>
    <p v-if="editorLocked && !editorBusy" role="status">草稿已保留，请重试保存；冲突请通过错误栏核对。</p>
    <div class="annotation-editor-actions"><button type="button" aria-label="取消" :disabled="editorBusy" @click="emit('cancel')">× 取消</button><button type="submit" aria-label="保存批注" :disabled="editorBusy || !editorOnPage.content?.trim()">{{ editorLocked ? '✓ 重试保存' : '✓ 保存' }}</button></div>
  </form>
</template>
