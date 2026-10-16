<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
const props=defineProps<{ content: string | null; color: string; fontSize: number }>()
const text=ref<HTMLElement>(), overflow=ref(false)
let observer: ResizeObserver | undefined
function measure() { if(text.value) overflow.value=text.value.scrollHeight>text.value.clientHeight+1 || text.value.scrollWidth>text.value.clientWidth+1 }
watch(()=>[props.content,props.fontSize],async()=>{await nextTick();measure()})
onMounted(()=>{observer=new ResizeObserver(measure);observer.observe(text.value!);measure()})
onBeforeUnmount(()=>observer?.disconnect())
</script>
<template>
  <div class="free-text-display" :title="overflow ? '内容超出文本框，双击编辑或增大文本框：'+content : undefined">
    <div ref="text" class="annotation-free-text" :style="{color,fontSize:fontSize+'px',lineHeight:1.25}">{{ content }}</div>
    <span v-if="overflow" class="free-text-overflow" aria-label="文本超出框，请双击编辑或增大文本框">…</span>
  </div>
</template>
