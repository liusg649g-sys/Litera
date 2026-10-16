<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { annotationLabels } from '../reader/annotations'
import type { AnnotationDTO } from '../reader/annotations'
import { annotationListFilters } from '../reader/state'
import AnnotationProperties from './AnnotationProperties.vue'
const props = defineProps<{ items: AnnotationDTO[]; selected: string; documentId: string; hasBackup?: boolean; hasPending?: boolean; editor?: AnnotationDTO | null; editorLocked?: boolean; editorBusy?: boolean }>()
const emit = defineEmits<{ select: [AnnotationDTO]; edit: [AnnotationDTO]; remove: [string]; exportBackup: []; savePending: []; draft: [AnnotationDTO]; save: []; cancel: [] }>()
const entriesWithDraft = computed(() => props.editor && !props.items.some(a=>a.id===props.editor!.id) ? [...props.items,props.editor] : props.items)
const filters = computed(() => annotationListFilters[props.documentId] ??= { type: '', color: '', sort: 'position' }), entries = ref<HTMLElement>()
const colors = computed(() => [...new Set(props.items.map(a => a.color))].sort())
const visible = computed(() => entriesWithDraft.value.filter(a => a.id===props.editor?.id || ((!filters.value.type || a.type===filters.value.type) && (!filters.value.color || a.color===filters.value.color))).sort((a,b) => filters.value.sort==='time' ? b.createdAt.localeCompare(a.createdAt) : a.pageNumber-b.pageNumber || position(a)-position(b) || a.createdAt.localeCompare(b.createdAt)))
function position(a: AnnotationDTO) { const g=a.geometry; return g.kind==='anchor' ? g.y : g.kind==='box' ? g.rect.y : g.positions[0]!.rects[0]!.y }
watch(() => props.editor?.id, async id => {
  if (!id) return
  await nextTick()
  entries.value?.querySelector<HTMLTextAreaElement>(`[data-list-annotation="${CSS.escape(id)}"] textarea`)?.focus({preventScroll:true})
})
watch(() => props.selected, async id => {
  const item = props.items.find(a => a.id===id)
  if (item && filters.value.type && filters.value.type!==item.type) filters.value.type=''
  if (item && filters.value.color && filters.value.color!==item.color) filters.value.color=''
  await nextTick()
  const scroller = entries.value, target = scroller?.querySelector<HTMLElement>(`[data-list-annotation="${CSS.escape(id)}"]`)
  if (!target || !scroller) return
  const r = target.getBoundingClientRect(), bounds = scroller.getBoundingClientRect()
  if (r.top < bounds.top + 8) scroller.scrollTop += r.top - bounds.top - 8
  else if (r.bottom > bounds.bottom - 8) scroller.scrollTop += r.bottom - bounds.bottom + 8
})
</script>
<template>
  <section class="annotation-list" aria-label="当前文献批注">
    <div class="annotation-list-controls"><strong>批注 ({{ items.length }})</strong><label>排序<select v-model="filters.sort" aria-label="批注排序"><option value="position">页码与位置</option><option value="time">创建时间</option></select></label><label>类型<select v-model="filters.type" aria-label="批注类型筛选"><option value="">全部类型</option><option v-for="(label,key) in annotationLabels" :key="key" :value="key">{{ label }}</option></select></label><label>颜色<select v-model="filters.color" aria-label="批注颜色筛选"><option value="">全部颜色</option><option v-for="c in colors" :key="c" :value="c">{{ c }}</option></select></label><button v-if="hasPending" type="button" @click="emit('savePending')">立即保存批注</button><button v-if="hasBackup" type="button" @click="emit('exportBackup')">导出草稿备份</button></div>
    <div ref="entries" class="annotation-list-items" tabindex="0" role="region" aria-label="批注条目">
    <p v-if="!visible.length" class="reader-panel-placeholder">{{ items.length ? '没有符合筛选条件的批注' : '此文献暂无批注，选择文本或使用注释工具开始。' }}</p>
    <article v-for="item in visible" :key="item.id" :data-list-annotation="item.id" :class="{ selected: selected===item.id }" class="annotation-card">
      <button class="annotation-card-main" @click="emit('select',item)"><span class="annotation-dot" :style="{ background: item.color }" /><strong>{{ annotationLabels[item.type] }} · 第 {{ item.pageNumber }} 页</strong><span v-if="editor?.id!==item.id" class="annotation-summary">{{ item.content || item.selectedText }}</span><time :datetime="item.createdAt">{{ new Date(item.createdAt).toLocaleString() }}</time></button>
      <form v-if="editor?.id===item.id" class="annotation-inline-form" @submit.prevent="emit('save')" @keydown.esc.stop.prevent="emit('cancel')">
        <textarea :value="editor.content || ''" aria-label="批注正文" rows="5" maxlength="20000" required :disabled="editorLocked" @input="emit('draft',{...editor,content:($event.target as HTMLTextAreaElement).value})" />
        <AnnotationProperties :item="editor" :disabled="editorLocked" @change="emit('draft',$event)" />
        <p v-if="editorLocked && !editorBusy" role="status">草稿已保留，请重试保存；冲突请通过错误栏核对。</p>
        <div class="annotation-editor-actions"><button type="button" aria-label="取消" :disabled="editorBusy" @click="emit('cancel')">× 取消</button><button type="submit" aria-label="保存批注" :disabled="editorBusy">{{ editorLocked ? '✓ 重试保存' : '✓ 保存' }}</button></div>
      </form>
      <div v-else class="annotation-card-actions"><button @click="emit('edit',item)">编辑</button><button @click="emit('remove',item.id)">删除</button></div>
    </article>
    </div>
  </section>
</template>
