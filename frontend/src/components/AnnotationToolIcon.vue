<script setup lang="ts">
defineProps<{ name: string }>()
</script>
<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name==='高亮'"><rect x="2.5" y="3" width="15" height="18" rx="1.5" fill="#F5D547" fill-opacity=".75" stroke="none"/><path d="m5.5 17 4.5-10.5L14.5 17 M7 13.5h6"/><path d="M21 4v16" opacity=".55"/></template>
    <template v-else-if="name==='下划线'"><path d="M6 3v8a6 6 0 0 0 12 0V3 M4 22h16"/></template>
    <template v-else-if="name==='波浪线'"><path d="m6 16 6-13 6 13 M8 12h8 M3 21q2-3 4 0t4 0t4 0t4 0t3 0"/></template>
    <template v-else-if="name==='删除线'"><path d="M17 5c-1-2-9-3-10 1-.6 2 1 3 4 4 M7 18c2 3 11 3 10-2 M3 12h18"/></template>
    <template v-else-if="name==='注释'"><path d="M4 3h16v13H9l-5 5z M8 7h8 M8 11h6"/></template>
    <template v-else-if="name==='自由文本'"><rect x="2" y="3" width="20" height="18" rx="2" stroke-dasharray="3 2"/><path d="M7 8h10 M12 8v9 M10 17h4"/></template>
    <template v-else-if="name==='手绘'"><path d="m5 15 11-12 4 4L9 19l-5 1z M14 5l4 4 M3 23q3-5 6-1t7-1"/></template>
    <template v-else><path d="m8 12 7-10 6 5-8 10z M8 12l-4 5 5 4 4-4 M2 23h12"/><path d="m5 18 3 2" stroke-width="3"/></template>
  </svg>
</template>
