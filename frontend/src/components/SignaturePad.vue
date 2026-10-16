<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
const emit=defineEmits<{confirm:[Blob];cancel:[];import:[]}>()
const canvas=ref<HTMLCanvasElement>(),hasInk=ref(false)
let cleanup:(()=>void)|undefined
function clear(){canvas.value?.getContext('2d')?.clearRect(0,0,600,200);hasInk.value=false}
function start(event:PointerEvent){
  if(event.button!==0)return
  const el=canvas.value!,ctx=el.getContext('2d')!,snapshot=ctx.getImageData(0,0,600,200),hadInk=hasInk.value
  const point=(e:PointerEvent)=>{const r=el.getBoundingClientRect();return {x:(e.clientX-r.left)*600/r.width,y:(e.clientY-r.top)*200/r.height}}
  let last=point(event);ctx.strokeStyle='#20242a';ctx.lineWidth=2;ctx.lineCap='round';ctx.lineJoin='round';el.setPointerCapture(event.pointerId);event.preventDefault()
  const move=(e:PointerEvent)=>{const p=point(e);ctx.beginPath();ctx.moveTo(last.x,last.y);ctx.lineTo(p.x,p.y);ctx.stroke();last=p;hasInk.value=true}
  const end=(e:PointerEvent)=>{if(e.type!=='pointerup'){ctx.putImageData(snapshot,0,0);hasInk.value=hadInk}finish()}
  const finish=()=>{el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',end);el.removeEventListener('lostpointercapture',end);window.removeEventListener('blur',cancel);if(el.hasPointerCapture(event.pointerId))el.releasePointerCapture(event.pointerId);cleanup=undefined}
  const cancel=()=>{ctx.putImageData(snapshot,0,0);hasInk.value=hadInk;finish()}
  cleanup=cancel;el.addEventListener('pointermove',move);el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end);el.addEventListener('lostpointercapture',end);window.addEventListener('blur',cancel)
}
function confirm(){if(hasInk.value)canvas.value?.toBlob(blob=>{if(blob)emit('confirm',blob)},'image/png')}
onBeforeUnmount(()=>cleanup?.())
</script>
<template><section class="signature-pad" aria-label="创建视觉签名" @keydown.stop @keydown.esc.prevent.stop="emit('cancel')" @pointerdown.stop><strong>手写签名</strong><p>在下方书写，完成后到 PDF 页面放置。</p><canvas ref="canvas" width="600" height="200" aria-label="签名画布" @pointerdown="start" /><div><button type="button" @click="clear">清空</button><button type="button" @click="emit('import')">导入签名图片</button><button type="button" @click="emit('cancel')">× 取消</button><button type="button" :disabled="!hasInk" @click="confirm">✓ 放置签名</button></div></section></template>
