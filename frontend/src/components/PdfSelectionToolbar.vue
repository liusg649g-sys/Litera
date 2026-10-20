<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import AnnotationToolIcon from './AnnotationToolIcon.vue'
import { annotationColors } from '../reader/annotations'
import { nativeFullscreenEscape } from '../reader/fullscreen'
const props=defineProps<{root:HTMLElement;documentId:string;enabled:boolean;color:string}>()
const emit=defineEmits<{choose:[string];color:[string]}>()
const panel=ref<HTMLElement>(),visible=ref(false),positioned=ref(false),opacity=ref(1),left=ref(0),top=ref(0)
const tools=['高亮','下划线','波浪线','删除线','注释']
const colorInput=ref<HTMLInputElement>()
let range:Range|null=null,revision=0,pickingColor=false
function close(){pickingColor=false;revision++;visible.value=false;positioned.value=false;range=null}
function selectedRange(){
  const s=window.getSelection()
  if(!s || s.isCollapsed || !s.rangeCount || !props.root.contains(s.anchorNode) || !props.root.contains(s.focusNode))return null
  const r=s.getRangeAt(0)
  const inText=(node:Node)=> (node instanceof Element?node:node.parentElement)?.closest('.textLayer')
  return r.toString().trim() && inText(r.startContainer) && inText(r.endContainer)?r:null
}
async function open(event:MouseEvent){
  if(!props.enabled)return
  const selected=selectedRange()
  if(!selected)return
  // A Range across pages also reports entire intervening canvas/page boxes.
  // Only use clipped text-node rectangles, just like the annotation producer.
  const rects:DOMRect[]=[]
  for(const span of props.root.querySelectorAll('.textLayer span:not(.markedContent)')){
    const node=span.firstChild
    if(!node || node.nodeType!==Node.TEXT_NODE || !selected.intersectsNode(node))continue
    const part=document.createRange();part.selectNodeContents(node)
    if(selected.compareBoundaryPoints(Range.START_TO_START,part)>0)part.setStart(selected.startContainer,selected.startOffset)
    if(selected.compareBoundaryPoints(Range.END_TO_END,part)<0)part.setEnd(selected.endContainer,selected.endOffset)
    if(!part.collapsed)rects.push(...[...part.getClientRects()].filter(r=>r.width>0 && r.height>0))
  }
  const keyboard=event.button!==2 || (event.clientX===0 && event.clientY===0)
  if(!keyboard && !rects.some(r=>event.clientX>=r.left && event.clientX<=r.right && event.clientY>=r.top && event.clientY<=r.bottom))return
  const bounds=props.root.getBoundingClientRect()
  const candidates=rects.filter(r=>r.bottom>bounds.top && r.top<bounds.bottom && r.right>bounds.left && r.left<bounds.right)
  // For a long/multi-page selection keep the panel near the line right-clicked,
  // so reaching it never requires crossing a distant part of the selection.
  const anchor=keyboard?candidates[0]:candidates.find(r=>event.clientX>=r.left && event.clientX<=r.right && event.clientY>=r.top && event.clientY<=r.bottom)
  if(!anchor)return
  event.preventDefault();event.stopPropagation()
  const token=++revision
  range=selected.cloneRange();visible.value=true;positioned.value=false;opacity.value=1
  await nextTick()
  if(token!==revision || !props.enabled || !panel.value)return
  const box=panel.value.getBoundingClientRect(),minX=Math.max(8,bounds.left+8),maxX=Math.min(window.innerWidth-8,bounds.right-8)
  left.value=Math.max(minX,Math.min(maxX-box.width,anchor.left))
  const minY=Math.max(8,bounds.top+8),maxY=Math.min(window.innerHeight-8,bounds.bottom-8)
  const above=anchor.top-box.height-8
  top.value=Math.max(minY,Math.min(maxY-box.height,above>=minY?above:anchor.bottom+8))
  positioned.value=true
  if(keyboard)panel.value.querySelector<HTMLButtonElement>('button')?.focus({preventScroll:true})
}
function move(event:PointerEvent){
  if(pickingColor || !visible.value || !positioned.value || !panel.value || (event.pointerType && event.pointerType!=='mouse'))return
  if(panel.value.contains(document.activeElement)){opacity.value=1;return}
  const r=panel.value.getBoundingClientRect()
  const distance=Math.hypot(Math.max(r.left-event.clientX,0,event.clientX-r.right),Math.max(r.top-event.clientY,0,event.clientY-r.bottom))
  opacity.value=Math.max(0,1-distance/50)
  if(distance>=50)close()
}
function selectionChanged(){
  if(pickingColor || !visible.value || !range)return
  const current=selectedRange()
  try{if(!current || current.compareBoundaryPoints(Range.START_TO_START,range)!==0 || current.compareBoundaryPoints(Range.END_TO_END,range)!==0)close()}catch{close()}
}
function outside(event:PointerEvent){if(event.target!==colorInput.value)finishColor();if(visible.value && !panel.value?.contains(event.target as Node))close()}
function keydown(event:KeyboardEvent){if(visible.value && event.key==='Escape' && !nativeFullscreenEscape()){event.preventDefault();event.stopPropagation();close()}}
function restoreSelection(){
  if(range && props.root.contains(range.startContainer) && props.root.contains(range.endContainer)){
    const selected=window.getSelection();selected?.removeAllRanges();selected?.addRange(range.cloneRange())
  }
}
function beginColor(){pickingColor=true;opacity.value=1}
function finishColor(){if(!pickingColor)return;pickingColor=false;if(props.enabled){colorInput.value?.blur();restoreSelection();opacity.value=1}}
function windowBlur(){if(!pickingColor)close()}
function chooseColor(value:string){if(props.enabled && /^#[0-9a-f]{6}$/i.test(value)){emit('color',value.toUpperCase());opacity.value=1}}
function choose(label:string){finishColor();if(props.enabled){if(!selectedRange())restoreSelection();if(selectedRange())emit('choose',label)}close()}
watch(()=>props.root,(root,_,cleanup)=>{root.addEventListener('contextmenu',open);cleanup(()=>root.removeEventListener('contextmenu',open))},{immediate:true})
watch(()=>[props.enabled,props.documentId],close)
onMounted(()=>{
  document.addEventListener('pointermove',move,{passive:true});document.addEventListener('pointerdown',outside,true)
  document.addEventListener('selectionchange',selectionChanged);document.addEventListener('keydown',keydown,true)
  window.addEventListener('scroll',close,true);window.addEventListener('resize',close);window.addEventListener('blur',windowBlur);window.addEventListener('focus',finishColor)
})
onBeforeUnmount(()=>{
  close();document.removeEventListener('pointermove',move);document.removeEventListener('pointerdown',outside,true)
  document.removeEventListener('selectionchange',selectionChanged);document.removeEventListener('keydown',keydown,true)
  window.removeEventListener('scroll',close,true);window.removeEventListener('resize',close);window.removeEventListener('blur',windowBlur);window.removeEventListener('focus',finishColor)
})
</script>
<template>
  <div v-if="visible" ref="panel" class="reader-selection-toolbar" role="toolbar" aria-label="选区批注快捷面板" :style="{left:left+'px',top:top+'px',opacity:positioned?opacity:0}" @pointerdown.prevent.stop @mousedown.prevent @contextmenu.prevent.stop @pointerenter="opacity=1" @focusin="opacity=1">
    <div class="selection-quick-actions" role="group" aria-label="快捷批注工具"><button v-for="label in tools" :key="label" type="button" :aria-label="label" :title="label" @click="choose(label)"><AnnotationToolIcon :name="label"/><span>{{ label }}</span></button></div>
    <div class="selection-quick-colors annotation-editor-colors" role="group" aria-label="快捷批注颜色选择"><span>颜色</span><button v-for="c in annotationColors" :key="c" type="button" class="reader-color" :style="{'--swatch':c}" :aria-label="`快捷批注颜色 ${c}`" :aria-pressed="color.toUpperCase()===c" @click="chooseColor(c)"/><label>自定义<input ref="colorInput" type="color" :value="color" aria-label="快捷批注自定义颜色" @pointerdown.stop="beginColor" @mousedown.stop @click="beginColor" @input="chooseColor(($event.target as HTMLInputElement).value)" @change="finishColor" @blur="finishColor" @cancel="finishColor"></label></div>
  </div>
</template>
