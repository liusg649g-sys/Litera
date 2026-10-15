<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
export interface OutlineNode { title: string; dest: string | any[] | null; items: OutlineNode[]; url?: string }
defineProps<{ items: OutlineNode[] }>()
const emit = defineEmits<{ navigate: [OutlineNode] }>()
const collapsed = ref(new Set<number>())
function toggle(index: number) { collapsed.value.has(index) ? collapsed.value.delete(index) : collapsed.value.add(index) }
</script>
<template><ul class="pdf-outline"><li v-for="(item, index) in items" :key="index"><div><button v-if="item.items.length" class="outline-toggle" :aria-label="`${collapsed.has(index) ? '展开' : '折叠'} ${item.title}`" :aria-expanded="!collapsed.has(index)" @click="toggle(index)"><component :is="collapsed.has(index) ? ArrowRight : ArrowDown" class="reader-chevron" aria-hidden="true" /></button><span v-else class="outline-toggle-placeholder" aria-hidden="true" /><button @click="emit('navigate', item)">{{ item.title || '未命名目录项' }}</button></div><PdfOutline v-if="item.items.length && !collapsed.has(index)" :items="item.items" @navigate="emit('navigate', $event)" /></li></ul></template>
