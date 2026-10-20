<script setup lang="ts">
import { nativeFullscreenEscape } from '../reader/fullscreen'
import { inject, shallowRef } from 'vue'
import { readerPopupRoot } from '../reader/fullscreen'
const popupRoot=inject(readerPopupRoot,shallowRef<HTMLElement>())
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { commentPopup,clearComment,dismissComment } from '../reader/commentPopup'
const props=defineProps<{documentId:string}>()
const tooltip=ref<{updatePopper:()=>void}>()
const reference=computed(()=>commentPopup.anchor as HTMLElement|undefined)
let observer:ResizeObserver|undefined,mutation:MutationObserver|undefined
function update(){
  if(!commentPopup.open)return
  if(!commentPopup.anchor?.isConnected){dismissComment();return}
  tooltip.value?.updatePopper()
}
watch(()=>props.documentId,clearComment,{immediate:true})
watch(()=>[commentPopup.anchor,commentPopup.open],async()=>{
  observer?.disconnect();mutation?.disconnect()
  if(!commentPopup.open || !commentPopup.anchor)return
  const host=commentPopup.anchor.closest('.pdf-page') || commentPopup.anchor
  observer=new ResizeObserver(update);observer.observe(host)
  mutation=new MutationObserver(update);mutation.observe(host,{childList:true,subtree:true})
  await nextTick();update()
})
function outside(event:PointerEvent){
  const path=event.composedPath()
  if(path.includes(commentPopup.anchor!) || path.some(el=>el instanceof Element && el.classList.contains('pdf-comment-popup')))return
  dismissComment()
}
function key(event:KeyboardEvent){if(event.key==='Escape' && !nativeFullscreenEscape())dismissComment()}
onMounted(()=>{document.addEventListener('pointerdown',outside,true);document.addEventListener('keydown',key);window.addEventListener('scroll',update,true);window.addEventListener('resize',update)})
onBeforeUnmount(()=>{observer?.disconnect();mutation?.disconnect();document.removeEventListener('pointerdown',outside,true);document.removeEventListener('keydown',key);window.removeEventListener('scroll',update,true);window.removeEventListener('resize',update);clearComment()})
</script>
<template>
  <el-tooltip :append-to="popupRoot" v-if="reference" ref="tooltip" :visible="commentPopup.open" :virtual-ref="reference" virtual-triggering effect="light" placement="top" popper-class="pdf-comment-popup" transition="pdf-comment-fade" :enterable="commentPopup.pinned" :show-after="0" :hide-after="0" :persistent="false" :popper-options="{strategy:'fixed'}">
    <template #content><div class="pdf-comment-popup-body">{{ commentPopup.content }}</div></template>
  </el-tooltip>
</template>
