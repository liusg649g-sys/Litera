<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
export interface OutlineNode { title: string; dest: string | any[] | null; items: OutlineNode[]; url?: string }
const props = defineProps<{ items: OutlineNode[] }>()
const emit = defineEmits<{ navigate: [OutlineNode] }>()
const expanded = ref(new Set<number>())
watch(() => props.items, () => expanded.value.clear())
function toggle(index: number) { expanded.value.has(index) ? expanded.value.delete(index) : expanded.value.add(index) }
</script>
<template><ul class="pdf-outline"><li v-for="(item, index) in items" :key="index"><div><button v-if="item.items.length" class="outline-toggle" :aria-label="`${expanded.has(index) ? '折叠' : '展开'} ${item.title}`" :aria-expanded="expanded.has(index)" @click="toggle(index)"><component :is="expanded.has(index) ? ArrowDown : ArrowRight" class="reader-chevron" aria-hidden="true" /></button><span v-else class="outline-toggle-placeholder" aria-hidden="true" /><button @click="emit('navigate', item)">{{ item.title || '未命名目录项' }}</button></div><PdfOutline v-if="item.items.length && expanded.has(index)" :items="item.items" @navigate="emit('navigate', $event)" /></li></ul></template>
