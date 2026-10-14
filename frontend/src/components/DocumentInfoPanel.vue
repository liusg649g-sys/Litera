<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { Download, View } from '@element-plus/icons-vue'
import { ApiError } from '../api'
import OverflowText from './OverflowText.vue'
import { contentUrl, getDocument, saveDocument, sizeLabel } from '../library'
import type { DocumentDTO, FolderDTO, TagDTO } from '../library'

const props = defineProps<{ folders?: FolderDTO[]; tags?: TagDTO[]; categoriesReady?: boolean }>()
const emit = defineEmits<{ saved: [document: DocumentDTO]; busy: [value: boolean]; read: [id: string] }>()
const selected = ref<DocumentDTO | null>(null), loading = ref(false), saving = ref(false)
const editing = ref(false), errorMessage = ref(''), conflict = ref(false), documentId = ref('')
const draft = ref({ title: '', authors: '', year: '', journal: '', doi: '', abstract: '', keywords: '', folderId: '', tagIds: [] as string[] })
const baseline = ref('')
const dirty = computed(() => editing.value && JSON.stringify(draft.value) !== baseline.value)
const confirming = ref(false), continueButton = ref<HTMLElement>(), confirmLayer = ref<HTMLElement>()
let revision = 0, resolveConfirmation: ((discard: boolean) => void) | null = null
let previousFocus: HTMLElement | null = null
function message(error: unknown) { return error instanceof Error ? error.message : '操作失败，请重试' }
function populate(document: DocumentDTO) {
  draft.value = { title: document.title, authors: document.authors.join('\n'), year: document.year?.toString() || '',
    journal: document.journal || '', doi: document.doi || '', abstract: document.abstract || '', keywords: document.keywords.join('\n'),
    folderId: document.folderId || '', tagIds: document.tags.map(tag => tag.id) }
  baseline.value = JSON.stringify(draft.value)
}
async function allowLeave() {
  if (saving.value || confirming.value) return false
  if (!dirty.value) return true
  previousFocus = document.activeElement as HTMLElement
  confirming.value = true
  const choice = new Promise<boolean>(resolve => { resolveConfirmation = resolve })
  await nextTick()
  continueButton.value?.querySelector<HTMLButtonElement>('button')?.focus()
  const discard = await choice
  if (discard) {
    if (selected.value) populate(selected.value)
    editing.value = false
  }
  return discard
}
function answer(discard: boolean) {
  const resolve = resolveConfirmation
  resolveConfirmation = null; confirming.value = false
  resolve?.(discard)
  if (!discard) void nextTick(() => { if (previousFocus?.isConnected) previousFocus.focus() })
}
function confirmKeys(event: KeyboardEvent) {
  event.stopPropagation()
  if (event.key === 'Escape') { event.preventDefault(); answer(false); return }
  if (event.key !== 'Tab') return
  const buttons = Array.from(confirmLayer.value?.querySelectorAll<HTMLButtonElement>('button') || [])
  const first = buttons[0], last = buttons[buttons.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
function captureConfirmationKeys(event: KeyboardEvent) {
  if (!confirming.value) return
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); answer(false) }
  else if (event.key === 'Tab' && !confirmLayer.value?.contains(document.activeElement)) {
    event.preventDefault(); event.stopPropagation()
    continueButton.value?.querySelector<HTMLButtonElement>('button')?.focus()
  }
}
async function open(id: string, edit = false, force = false) {
  if (id === documentId.value && selected.value && !force) {
    if (edit) editing.value = true
    return true
  }
  if (!await allowLeave()) return false
  const requestRevision = ++revision
  documentId.value = id; loading.value = true; selected.value = null
  editing.value = false; conflict.value = false; errorMessage.value = ''
  try {
    const document = await getDocument(id)
    if (requestRevision !== revision) return false
    selected.value = document; populate(document); editing.value = edit
  } catch (error) { if (requestRevision === revision) errorMessage.value = message(error) }
  finally { if (requestRevision === revision) loading.value = false }
  return requestRevision === revision
}
async function cancelEdit() {
  if (!await allowLeave()) return
  if (selected.value) populate(selected.value)
  editing.value = false; errorMessage.value = ''; conflict.value = false
}
function sync(document: DocumentDTO) {
  if (document.id !== documentId.value || dirty.value || saving.value) return
  ++revision; selected.value = document; loading.value = false; populate(document)
  errorMessage.value = ''; conflict.value = false
}
function lines(value: string) { return value.split('\n').map(item => item.trim()).filter(Boolean) }
async function save() {
  if (!selected.value || saving.value || conflict.value) return
  errorMessage.value = ''
  const yearText = draft.value.year.trim(), year = yearText ? Number(yearText) : null
  if (!draft.value.title.trim()) { errorMessage.value = '标题不能为空'; return }
  if (year !== null && (!/^\d{1,4}$/.test(yearText) || year < 1 || year > 9999)) { errorMessage.value = '年份请输入 1–9999 的整数，或留空'; return }
  saving.value = true; emit('busy', true)
  try {
    const document = await saveDocument(selected.value.id, { version: selected.value.version, title: draft.value.title.trim(),
      authors: lines(draft.value.authors), keywords: lines(draft.value.keywords), year,
      journal: draft.value.journal.trim() || null, doi: draft.value.doi.trim() || null, abstract: draft.value.abstract.trim() || null,
      ...(props.categoriesReady ? { folderId: draft.value.folderId || null, tagIds: draft.value.tagIds } : {}) })
    selected.value = document; populate(document); editing.value = false; conflict.value = false
    emit('saved', document)
  } catch (error) { errorMessage.value = message(error); conflict.value = error instanceof ApiError && error.code === 'VERSION_CONFLICT' }
  finally { saving.value = false; emit('busy', false) }
}
function dateLabel(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function beforeUnload(event: BeforeUnloadEvent) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); window.addEventListener('keydown', captureConfirmationKeys, true) })
onUnmounted(() => { ++revision; resolveConfirmation?.(false); resolveConfirmation = null; window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('keydown', captureConfirmationKeys, true) })
defineExpose({ open, allowLeave, sync })
</script>
<template>
  <div class="info-panel-content" :aria-busy="loading || saving" :inert="confirming">
    <p v-if="loading" class="panel-state" role="status">正在读取文献信息…</p>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />
    <el-button v-if="!selected && !loading" @click="open(documentId, false, true)">重试加载文献</el-button>
    <template v-if="selected">
      <form v-if="editing" class="metadata-form" @submit.prevent="save">
        <label>标题<input v-model="draft.title" maxlength="500" required :disabled="saving"></label>
        <label>作者（每行一位）<textarea v-model="draft.authors" rows="3" :disabled="saving" /></label>
        <div class="metadata-columns"><label>年份<input v-model="draft.year" inputmode="numeric" maxlength="4" :disabled="saving"></label><label>期刊<input v-model="draft.journal" maxlength="500" :disabled="saving"></label></div>
        <label>DOI<input v-model="draft.doi" maxlength="255" :disabled="saving"></label>
        <label>摘要<textarea v-model="draft.abstract" maxlength="50000" rows="5" :disabled="saving" /></label>
        <label>关键词（每行一个）<textarea v-model="draft.keywords" rows="3" :disabled="saving" /></label>
        <div class="classification-field"><label for="document-folder">所属文件夹</label><el-select id="document-folder" v-model="draft.folderId" :empty-values="[null, undefined]" class="library-select" aria-label="文献所属文件夹" popper-class="library-select-menu" :teleported="true" :disabled="saving || !categoriesReady"><el-option label="未分类" value="" /><el-option v-for="folder in folders" :key="folder.id" :label="folder.name" :value="folder.id" /></el-select></div>
        <div class="classification-field"><span id="document-tags-label">标签</span><el-checkbox-group v-model="draft.tagIds" class="tag-choices panel-tag-list" aria-labelledby="document-tags-label" :disabled="saving || !categoriesReady"><el-checkbox v-for="tag in tags" :key="tag.id" :value="tag.id"><OverflowText :text="tag.name" /></el-checkbox></el-checkbox-group><small v-if="!tags?.length" class="field-hint">暂无标签，请在标签管理中创建。</small></div>
        <p class="muted">仅修改题录，原始 PDF 保持不变。</p>
        <div class="panel-edit-actions"><el-button type="primary" native-type="submit" :loading="saving" :disabled="conflict">保存题录</el-button><el-button :disabled="saving" @click="cancelEdit">取消编辑</el-button><el-button v-if="conflict" @click="open(documentId, false, true)">放弃草稿并载入最新版本</el-button></div>
      </form>
      <template v-else>
        <h3 class="detail-title">{{ selected.title }}</h3>
        <div class="panel-document-actions"><el-button size="small" type="primary" @click="editing = true">编辑题录</el-button><a class="pdf-action" :href="contentUrl(selected.id)" target="_blank" rel="noopener" @click.prevent="emit('read', selected.id)"><View />预览 PDF</a><a class="pdf-action" :href="contentUrl(selected.id, true)"><Download />下载 PDF</a></div>
        <section class="info-group"><h3>题录信息</h3><dl class="metadata-details">
          <dt>作者</dt><dd :class="{ 'empty-value': !selected.authors.length }">{{ selected.authors.join('、') || '未填写' }}</dd>
          <dt>发表年份</dt><dd :class="{ 'empty-value': !selected.year }">{{ selected.year ?? '未填写' }}</dd>
          <dt>期刊</dt><dd :class="{ 'empty-value': !selected.journal }">{{ selected.journal || '未填写' }}</dd>
          <dt>DOI</dt><dd :class="{ 'empty-value': !selected.doi }">{{ selected.doi || '未填写' }}</dd>
        </dl></section>
        <section class="info-group"><h3>摘要与关键词</h3><p class="abstract-text" :class="{ 'empty-value': !selected.abstract }">{{ selected.abstract || '未填写' }}</p><dl class="metadata-details"><dt>关键词</dt><dd :class="{ 'empty-value': !selected.keywords.length }">{{ selected.keywords.join('、') || '未填写' }}</dd></dl></section>
        <section class="info-group"><h3>分类</h3><dl class="metadata-details"><dt>所属文件夹</dt><dd>{{ folders?.find(folder => folder.id === selected?.folderId)?.name || (selected.folderId ? '加载中' : '未分类') }}</dd><dt>标签</dt><dd :class="{ 'empty-value': !selected.tags.length }">{{ selected.tags.map(tag => tag.name).join('、') || '未填写' }}</dd></dl></section>
        <section class="info-group"><h3>文件信息</h3><dl class="metadata-details"><dt>文件名称</dt><dd>{{ selected.attachment.originalName }}</dd><dt>文件大小</dt><dd>{{ sizeLabel(selected.attachment.sizeBytes) }}</dd><dt>上传时间</dt><dd>{{ dateLabel(selected.createdAt) }}</dd></dl></section>
        <p class="field-hint">阅读当前通过浏览器预览原始 PDF；在线阅读器待实现。</p>
      </template>
    </template>
  </div>
  <div v-if="confirming" ref="confirmLayer" class="panel-unsaved-overlay" @click.self="answer(false)" @keydown="confirmKeys">
    <section class="panel-unsaved-dialog" role="alertdialog" aria-modal="true" aria-labelledby="unsaved-title" aria-describedby="unsaved-description">
      <h3 id="unsaved-title">未保存的修改</h3>
      <p id="unsaved-description">题录修改尚未保存，是否放弃这些修改？</p>
      <div class="panel-unsaved-actions"><span ref="continueButton"><el-button size="small" @click="answer(false)">继续编辑</el-button></span><el-button type="primary" size="small" @click="answer(true)">放弃修改</el-button></div>
    </section>
  </div>
</template>
