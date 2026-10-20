<script setup lang="ts">
import { nativeFullscreenEscape } from '../reader/fullscreen'
import { computed, shallowRef, watch, onBeforeUnmount } from 'vue'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import { normalizedToViewport, viewportToNormalized } from '../reader/state'
import { annotationLabels, type AnnotationDTO, type AnnotationType, type Geometry } from '../reader/annotations'
import { bounds, drawingTypes, dragRect, resizeObject, transformGeometry, liveInk, drawingViewports, rotateBoxPoint, resizeRotatedObject } from '../reader/objectGeometry'
import { boxHandles, type BoxHandle } from '../reader/boxGeometry'
import type { NormalizedRect } from '../reader/context'
import { assetUrl, type ReaderAsset } from '../reader/assets'
import AnnotationProperties from './AnnotationProperties.vue'
const props=defineProps<{pdf:PDFDocumentProxy;documentId:string;pageNumber:number;scale:number;items:AnnotationDTO[];selected:string;tool:AnnotationType|'erase'|'';enabled:boolean;group:string;editor?:AnnotationDTO|null;locked?:boolean;busy?:boolean;editingActive?:boolean;color:string;lineWidth:number;opacity:number;placement?:ReaderAsset|null}>()
const emit=defineEmits<{select:[AnnotationDTO];edit:[AnnotationDTO];draft:[AnnotationDTO];save:[];cancel:[];draw:[AnnotationType,Geometry];move:[string,Geometry];warning:[string];replaceAsset:[]}>()
const page=shallowRef<PDFPageProxy>()
watch(()=>[props.pdf,props.pageNumber] as const,async([pdf,n])=>{const p=await pdf.getPage(n);if(props.pdf===pdf && props.pageNumber===n) page.value=p},{immediate:true})
const vp=computed(()=>page.value?.getViewport({scale:props.scale}))
watch(vp,value=>{if(value){let pages=drawingViewports.get(props.pdf);if(!pages){pages=new Map();drawingViewports.set(props.pdf,pages)}pages.set(props.pageNumber,value)}})

const preview=shallowRef<AnnotationDTO|null>(null), ghost=shallowRef<Geometry|null>(null)
const editorHere=computed(()=>props.editor?.pageNumber===props.pageNumber && drawingTypes.includes(props.editor.type)?props.editor:null)
const creating=computed(()=>props.enabled && drawingTypes.includes(props.tool) && !props.editingActive)
function editable(a:AnnotationDTO){return props.group===(['rectangle','circle','ellipse'].includes(a.type)?'形状':['image','signature','watermark'].includes(a.type)?'插入':'批注')}
const active=computed(()=>props.enabled && !props.tool)
// Erasing needs object hit testing, but must not enable selection handles/dragging.
const erasing=computed(()=>props.enabled && props.tool==='erase' && !props.editingActive)
const items=computed(()=>{
  const all=props.items.filter(a=>drawingTypes.includes(a.type) && a.pageNumber===props.pageNumber)
  if(editorHere.value && !all.some(a=>a.id===editorHere.value!.id)) all.push(editorHere.value)
  return all.map(a=>preview.value?.id===a.id?preview.value:editorHere.value?.id===a.id?editorHere.value:a).sort((a,b)=>(active.value ? Number(a.id===props.selected)-Number(b.id===props.selected) : 0) || a.zIndex-b.zIndex)
})
function point(x:number,y:number){return vp.value?normalizedToViewport(vp.value,x,y):[0,0]}
function physical(){return {w:page.value!.view[2]!-page.value!.view[0]!,h:page.value!.view[3]!-page.value!.view[1]!}}
function local(e:PointerEvent|MouseEvent){const r=(e.currentTarget as Element).closest('svg')!.getBoundingClientRect();return viewportToNormalized(vp.value!,(e.clientX-r.left)*vp.value!.width/r.width,(e.clientY-r.top)*vp.value!.height/r.height)}
function clamp(p:{x:number;y:number}){return {x:Math.max(0,Math.min(1,p.x)),y:Math.max(0,Math.min(1,p.y))}}
function matrix(r:NormalizedRect){const a=point(r.x,r.y),b=point(r.x+r.width,r.y),c=point(r.x,r.y+r.height),{w,h}=physical();return `matrix(${(b[0]!-a[0]!)/(r.width*w)} ${(b[1]!-a[1]!)/(r.width*w)} ${(c[0]!-a[0]!)/(r.height*h)} ${(c[1]!-a[1]!)/(r.height*h)} ${a[0]} ${a[1]})`}
function path(g:Geometry){return g.kind==='points'?g.points.map((p,i)=>`${i?'L':'M'} ${point(p.x,p.y).join(' ')}`).join(' '):''}
function objectPoint(g:Geometry,x:number,y:number){
  if(g.kind==='box' && g.rotation){const {w,h}=physical();const p=rotateBoxPoint({x,y},g.rect,g.rotation,w/h);return point(p.x,p.y)}
  return point(x,y)
}
function selectionGeometry(a:AnnotationDTO,g:Geometry=a.geometry):Geometry{return a.type==='watermark' && g.kind==='box'?{...g,rotation:0}:g}
function polygon(g:Geometry){const r=bounds(g);return [[r.x,r.y],[r.x+r.width,r.y],[r.x+r.width,r.y+r.height],[r.x,r.y+r.height]].map(([x,y])=>objectPoint(g,x!,y!).join(',')).join(' ')}
function handle(g:Geometry,h:BoxHandle){const r=bounds(g);return objectPoint(g,r.x+(h.includes('w')?0:h.includes('e')?r.width:r.width/2),r.y+(h.includes('n')?0:h.includes('s')?r.height:r.height/2))}
let cancelGesture:(()=>void)|undefined,skipClick=false
function capture(e:PointerEvent,move:(e:PointerEvent)=>void,finish:(e:PointerEvent)=>void,onCleanup=()=>{}){
  const el=e.currentTarget as SVGElement;e.preventDefault();e.stopPropagation();el.setPointerCapture(e.pointerId)
  const end=(event:PointerEvent)=>{finish(event);cleanup()}
  const escape=(event:KeyboardEvent)=>{if(event.key==='Escape' && !nativeFullscreenEscape()){event.preventDefault();event.stopImmediatePropagation();skipClick=true;cleanup()}}
  function cleanup(){onCleanup();el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',cleanup);el.removeEventListener('lostpointercapture',cleanup);window.removeEventListener('blur',cleanup);document.removeEventListener('keydown',escape,true);if(el.hasPointerCapture(e.pointerId))el.releasePointerCapture(e.pointerId);preview.value=null;ghost.value=null;liveInk.value=null;cancelGesture=undefined;document.body.classList.remove('annotation-dragging')}
  cancelGesture=cleanup;el.addEventListener('pointermove',move);el.addEventListener('pointerup',end);el.addEventListener('pointercancel',cleanup);el.addEventListener('lostpointercapture',cleanup);window.addEventListener('blur',cleanup);document.addEventListener('keydown',escape,true);document.body.classList.add('annotation-dragging')
}
watch(()=>[props.scale,props.enabled,props.tool,props.pdf,props.pageNumber],()=>{cancelGesture?.();ghost.value=null})
onBeforeUnmount(()=>cancelGesture?.())
function begin(e:PointerEvent){
  skipClick=false
  if(!creating.value || !vp.value || e.button!==0 || ['image','signature','watermark'].includes(props.tool))return
  const start=clamp(local(e)),type=props.tool as AnnotationType,started=performance.now();let exceeded=false,total=1,length=0
  let segment:Extract<Geometry,{kind:'points'}>|undefined={kind:'points',pageNumber:props.pageNumber,points:[start]}
  const segments=[segment]
  let frame=0
  const publish=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=0;liveInk.value={documentId:props.documentId,segments:segments.map(g=>({...g,points:[...g.points]}))}})}
  const update=(event:PointerEvent)=>{
    if(type==='ink'){
      const samples=event.getCoalescedEvents?.() || [event]
      for(const sample of samples.length?samples:[event]){
        const host=document.elementsFromPoint(sample.clientX,sample.clientY).map(el=>el.closest<HTMLElement>('.pdf-page')).find(Boolean)
        if(!host){segment=undefined;continue}
        const n=Number(host.dataset.page),viewport=drawingViewports.get(props.pdf)?.get(n)
        if(!viewport)continue
        const r=host.getBoundingClientRect(),p=clamp(viewportToNormalized(viewport,(sample.clientX-r.left)*viewport.width/r.width,(sample.clientY-r.top)*viewport.height/r.height))
        if(!segment || segment.pageNumber!==n){segment={kind:'points',pageNumber:n,points:[p]};segments.push(segment);total++;continue}
        const last=segment.points[segment.points.length-1]!,distance=Math.hypot((p.x-last.x)*viewport.width,(p.y-last.y)*viewport.height)
        if(distance<1.2)continue
        if(total>=10000 || performance.now()-started>60000 || length+distance>100000){exceeded=true;break}
        segment.points.push(p);total++;length+=distance
      }
      publish()
    }else{const {w,h}=physical();ghost.value={kind:'box',pageNumber:props.pageNumber,rotation:0,rect:dragRect(start,clamp(local(event)),type==='circle'?h/w:undefined)}}
  }
  capture(e,update,event=>{update(event);cancelAnimationFrame(frame);if(exceeded){emit('warning','单笔最多10000点、60秒或100000屏幕像素，请分成多笔绘制。');return}
    if(type==='ink'){for(const g of segments)if(g.points.length>1)emit('draw',type,g)}
    else if(ghost.value){const r=bounds(ghost.value);if(r.width*vp.value!.width>3 && r.height*vp.value!.height>3)emit('draw',type,ghost.value)}
  },()=>cancelAnimationFrame(frame))
}

function hover(e:PointerEvent){
  if(!creating.value || !['image','signature','watermark'].includes(props.tool))return
  const p=clamp(local(e)),{w,h}=physical(),ratio=props.placement?props.placement.width/props.placement.height:3
  const width=Math.min(.32,.35*h/w*ratio),height=width*w/h/ratio
  ghost.value={kind:'box',pageNumber:props.pageNumber,rotation:0,rect:{x:Math.min(1-width,Math.max(0,p.x-width/2)),y:Math.min(1-height,Math.max(0,p.y-height/2)),width,height}}
}
function place(e:MouseEvent){if(creating.value && !ghost.value)hover(e as PointerEvent);if(creating.value && ['image','signature','watermark'].includes(props.tool) && ghost.value){e.stopPropagation();emit('draw',props.tool as AnnotationType,ghost.value);ghost.value=null}}
function select(a:AnnotationDTO){if(!skipClick)emit('select',a)}
function drag(e:PointerEvent,a:AnnotationDTO,h?:BoxHandle){
  skipClick=false
  if(!active.value || !editable(a) || props.locked || e.button!==0 || (props.editingActive && props.editor?.id!==a.id))return
  emit('select',a);const start=local(e),r=bounds(a.geometry);let latest=a.geometry,moved=false
  capture(e,event=>{const p=local(event),dx=p.x-start.x,dy=p.y-start.y;moved ||= Math.hypot(event.clientX-e.clientX,event.clientY-e.clientY)>3;if(!moved)return
    const next=h?(a.geometry.kind==='box' && a.geometry.rotation && ['image','signature'].includes(a.type)?resizeRotatedObject(r,dx,dy,h,a.geometry.rotation,physical().w/physical().h):resizeObject(r,dx,dy,h,['circle','image','signature'].includes(a.type)?r.width/r.height:undefined)):{...r,x:Math.max(0,Math.min(1-r.width,r.x+dx)),y:Math.max(0,Math.min(1-r.height,r.y+dy))}
    latest=transformGeometry(a.geometry,next);preview.value={...a,geometry:latest}
  },()=>{skipClick=moved;if(moved)emit('move',a.id,latest)})
}
function changeAngle(event:Event){
  const input=event.target as HTMLInputElement,item=editorHere.value
  if(!item || item.geometry.kind!=='box' || !input.value.trim() || !Number.isFinite(input.valueAsNumber))return
  const rotation=Math.max(-90,Math.min(90,Math.round(input.valueAsNumber)))
  input.value=String(rotation)
  emit('draft',{...item,geometry:{...item.geometry,rotation}})
}
// Anchor the editor to the unrotated box so angle changes do not move its inputs.
const controls=computed(()=>{if(!editorHere.value || !vp.value)return {};const r=bounds(preview.value?.geometry || editorHere.value.geometry),corners=[[r.x,r.y],[r.x+r.width,r.y+r.height],[r.x+r.width,r.y],[r.x,r.y+r.height]].map(([x,y])=>point(x!,y!));const left=Math.min(...corners.map(p=>p[0]!)),top=Math.min(...corners.map(p=>p[1]!)),bottom=Math.max(...corners.map(p=>p[1]!));return {left:Math.max(4,Math.min(vp.value.width-292,left))+'px',top:Math.max(4,bottom+210<vp.value.height?bottom+8:top-210)+'px',maxWidth:Math.max(100,vp.value.width-8)+'px'}})
const ghostItem=computed(()=>{if(!ghost.value)return null;return {id:'preview',type:props.tool,geometry:ghost.value,color:props.color,style:{opacity:props.opacity,lineWidth:props.lineWidth,fontSize:30},content:'水印',assetId:props.placement?.assetId,documentId:props.documentId} as AnnotationDTO})
const paintItems=computed(()=>{
  const all=ghostItem.value?[...items.value,ghostItem.value]:[...items.value]
  if(liveInk.value?.documentId===props.documentId)for(const [i,g] of liveInk.value.segments.entries())if(g.pageNumber===props.pageNumber)all.push({id:'ink-preview-'+i,type:'ink',geometry:g,color:props.color,style:{opacity:props.opacity,lineWidth:props.lineWidth}} as AnnotationDTO)
  return all
})
</script>
<template>
  <svg v-if="vp" class="reader-object-layer drawing-overlay" :class="{creating,active,erasing}" :width="vp.width" :height="vp.height" :viewBox="`0 0 ${vp.width} ${vp.height}`" @pointerdown.self="begin" @pointermove="hover" @pointerleave="!cancelGesture && (ghost=null)" @click="place">
    <g v-for="a in paintItems" :key="a.id" :data-drawing="a.id" :data-annotation="a.id.includes('preview')?undefined:a.id" class="drawing-object" :class="{'drag-preview':preview?.id===a.id,'drawing-ghost':a.id.includes('preview')}" @pointerdown="drag($event,a)" @click.stop="select(a)" @dblclick.stop="active && emit('edit',a)">
      <path v-if="a.geometry.kind==='points'" :d="path(a.geometry)" :stroke="a.color" :stroke-width="(a.style.lineWidth||2)*scale" :opacity="a.style.opacity" fill="none" stroke-linecap="round" stroke-linejoin="round" />
      <g v-else-if="a.geometry.kind==='box'" :transform="matrix(a.geometry.rect)" :opacity="a.style.opacity">
        <rect v-if="a.type==='rectangle'" x="0" y="0" :width="a.geometry.rect.width*physical().w" :height="a.geometry.rect.height*physical().h" :fill="a.style.fill||'none'" :stroke="a.color" :stroke-width="(a.style.lineWidth||1)/page!.userUnit" />
        <ellipse v-if="['circle','ellipse'].includes(a.type)" :cx="a.geometry.rect.width*physical().w/2" :cy="a.geometry.rect.height*physical().h/2" :rx="a.geometry.rect.width*physical().w/2" :ry="a.geometry.rect.height*physical().h/2" :fill="a.style.fill||'none'" :stroke="a.color" :stroke-width="(a.style.lineWidth||1)/page!.userUnit" />
        <image v-if="['image','signature'].includes(a.type) && a.assetId" :href="assetUrl(documentId,a.assetId)" :transform="`rotate(${a.geometry.rotation} ${a.geometry.rect.width*physical().w/2} ${a.geometry.rect.height*physical().h/2})`" :width="a.geometry.rect.width*physical().w" :height="a.geometry.rect.height*physical().h" preserveAspectRatio="xMidYMid meet" @error="emit('warning',a.type==='signature'?'签名加载失败，请检查网络。':'图片加载失败，请检查网络或更换图片。')" />
        <svg v-if="a.type==='watermark'" :style="{width:a.geometry.rect.width*physical().w+'px',height:a.geometry.rect.height*physical().h+'px'}" :width="a.geometry.rect.width*physical().w" :height="a.geometry.rect.height*physical().h" overflow="hidden"><text :x="a.geometry.rect.width*physical().w/2" :y="a.geometry.rect.height*physical().h/2" dominant-baseline="middle" text-anchor="middle" :fill="a.color" :font-size="(a.style.fontSize||30)/page!.userUnit" :transform="`rotate(${a.geometry.rotation} ${a.geometry.rect.width*physical().w/2} ${a.geometry.rect.height*physical().h/2})`">{{ a.content }}</text></svg>
      </g>
      <polygon v-if="active && editable(a) && selected===a.id" :points="polygon(selectionGeometry(a))" fill="transparent" stroke="#9B0000" stroke-width="1" stroke-dasharray="4 3" class="drawing-selection" />
      <template v-if="active && editable(a) && selected===a.id && !locked"><circle v-for="h in (['circle','image','signature'].includes(a.type)?(['nw','ne','se','sw'] as const):boxHandles)" :key="h" :data-handle="h" :cx="handle(selectionGeometry(a),h)[0]" :cy="handle(selectionGeometry(a),h)[1]" r="4" fill="white" stroke="#9B0000" :style="{cursor:h+'-resize'}" @pointerdown.stop="drag($event,a,h)" /></template>
    </g>
  </svg>
  <form v-if="editorHere" class="free-text-controls drawing-controls" :style="controls" @submit.prevent="emit('save')" @pointerdown.stop @click.stop @keydown="$event.key!=='Escape' || !nativeFullscreenEscape() ? $event.stopPropagation() : undefined" @keydown.esc="!nativeFullscreenEscape() && ($event.preventDefault(),$event.stopPropagation(),emit('cancel'))">
    <strong>{{ annotationLabels[editorHere.type] }} · 第 {{ pageNumber }} 页</strong>
    <label v-if="editorHere.type==='watermark'">内容<input aria-label="水印内容" :value="editorHere.content" maxlength="200" required :disabled="locked" @input="emit('draft',{...editorHere,content:($event.target as HTMLInputElement).value})"></label>
    <AnnotationProperties :item="editorHere" :disabled="locked" @change="emit('draft',$event)" />
    <label v-if="['watermark','image','signature'].includes(editorHere.type) && editorHere.geometry.kind==='box'" class="drawing-angle">角度
      <input type="range" min="-90" max="90" step="1" :aria-label="`${annotationLabels[editorHere.type]}角度`" :value="editorHere.geometry.rotation" :disabled="locked" @input="changeAngle">
      <input type="number" min="-90" max="90" step="1" required :aria-label="`${annotationLabels[editorHere.type]}角度数值`" :value="editorHere.geometry.rotation" :disabled="locked" @input="changeAngle" @blur="($event.target as HTMLInputElement).value=String(editorHere.geometry.rotation)">°
    </label>
    <p v-if="editorHere.type==='watermark'" class="free-text-overflow-hint">水印按框显示；文字超出时请增大边框或减小字号。</p>
    <div v-if="editorHere.type==='image'">
      <button type="button" :disabled="busy" @click="emit('replaceAsset')">更换图片</button>
    </div>
    <p v-if="locked && !busy">草稿已保留，请重试保存；冲突请通过错误栏核对。</p>
    <div class="annotation-editor-actions"><button type="button" aria-label="取消" :disabled="busy" @click="emit('cancel')">× 取消</button><button type="submit" aria-label="保存批注" :disabled="busy">{{ locked?'✓ 重试保存':'✓ 保存' }}</button></div>
  </form>
</template>
