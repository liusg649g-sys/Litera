<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AnnotationType } from 'pdfjs-dist'
import type { PDFPageProxy } from 'pdfjs-dist'
import { showComment,leaveComment } from '../reader/commentPopup'
const props=defineProps<{page:PDFPageProxy;scale:number;enabled:boolean}>()
const notes=ref<{id:string;content:string;rect:number[]}[]>([])
watch(()=>props.page,async page=>{
  notes.value=[]
  try{
    const annotations=await page.getAnnotations({intent:'display'})
    if(page!==props.page)return
    notes.value=annotations.filter(a=>a.annotationType===AnnotationType.TEXT && a.contentsObj?.str && a.rect?.length===4)
      .map(a=>({id:a.id,content:a.contentsObj.str,rect:a.rect}))
  }catch{ /* Original PDF rendering remains usable if annotation metadata is malformed. */ }
},{immediate:true})
const boxes=computed(()=>{
  const viewport=props.page.getViewport({scale:props.scale})
  return notes.value.map(note=>{const [x1,y1]=viewport.convertToViewportPoint(note.rect[0]!,note.rect[1]!),[x2,y2]=viewport.convertToViewportPoint(note.rect[2]!,note.rect[3]!);return {...note,x:Math.min(x1!,x2!),y:Math.min(y1!,y2!),width:Math.abs(x2!-x1!),height:Math.abs(y2!-y1!)}})
})
</script>
<template>
  <svg v-if="enabled && boxes.length" class="reader-object-layer native-pdf-comments" aria-label="PDF原生批注">
    <rect v-for="note in boxes" :key="note.id" :data-native-comment="note.id" :x="note.x" :y="note.y" :width="note.width" :height="note.height" fill="transparent" role="button" tabindex="0" :aria-label="`PDF批注 ${note.content}`" @mouseenter="showComment('native:'+note.id,note.content,$event.currentTarget as Element)" @mouseleave="leaveComment('native:'+note.id)" @click.stop="showComment('native:'+note.id,note.content,$event.currentTarget as Element,true)" @keydown.enter.prevent="showComment('native:'+note.id,note.content,$event.currentTarget as Element,true)" />
  </svg>
</template>
