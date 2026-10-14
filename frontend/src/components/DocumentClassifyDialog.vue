<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import LibraryActionDialog from './LibraryActionDialog.vue'
import OverflowText from './OverflowText.vue'
import { ApiError } from '../api'
import { getDocument, listFolders, listTags, saveDocument } from '../library'
import type { DocumentDTO, FolderDTO, TagDTO } from '../library'

const props = defineProps<{ documentId: string; kind: 'move' | 'tags' }>()
const emit = defineEmits<{ close: []; saved: [document: DocumentDTO]; busy: [value: boolean] }>()
const selected = ref<DocumentDTO>(), folders = ref<FolderDTO[]>([]), tags = ref<TagDTO[]>([])
const folderId = ref(''), tagIds = ref<string[]>([]), loading = ref(true), saving = ref(false), error = ref(''), conflict = ref(false)
const currentFolder = computed(() => folders.value.find(folder => folder.id === selected.value?.folderId)?.name || '未分类')
let revision = 0
async function load(preserve = false) {
  const request = ++revision
  loading.value = true; error.value = ''
  try {
    const [document, availableFolders, availableTags] = await Promise.all([getDocument(props.documentId), listFolders(), listTags()])
    if (request !== revision) return
    selected.value = document; folders.value = availableFolders; tags.value = availableTags; conflict.value = false
    if (!preserve) { folderId.value = document.folderId || ''; tagIds.value = document.tags.map(tag => tag.id) }
  } catch (reason) { if (request === revision) error.value = reason instanceof Error ? reason.message : '加载失败，请重试' }
  finally { if (request === revision) loading.value = false }
}
async function save() {
  if (!selected.value || loading.value || saving.value || conflict.value) return
  saving.value = true; emit('busy', true); error.value = ''
  try {
    const document = await saveDocument(selected.value.id, { version: selected.value.version,
      ...(props.kind === 'move' ? { folderId: folderId.value || null } : { tagIds: tagIds.value }) })
    emit('saved', document)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '保存失败，请重试'
    conflict.value = reason instanceof ApiError && reason.code === 'VERSION_CONFLICT'
  } finally { saving.value = false; emit('busy', false) }
}
onMounted(() => void load())
onUnmounted(() => { ++revision })
</script>
<template>
  <LibraryActionDialog :title="kind === 'move' ? '移动到文件夹' : '管理文献标签'" :busy="saving" :error="error" :confirm="kind === 'move' ? '确定' : '保存'" :confirm-disabled="loading || !selected || conflict" dialog-class="document-classify-dialog" @close="emit('close')" @confirm="save">
    <p v-if="loading" class="quick-state" role="status">正在加载文献及分类…</p>
    <template v-else-if="selected">
      <OverflowText class="quick-document-title" :text="selected.title" />
      <template v-if="kind === 'move'">
        <p class="current-folder">当前所属文件夹：{{ currentFolder }}</p>
        <div class="classification-field"><label for="quick-folder">目标文件夹</label><el-select id="quick-folder" v-model="folderId" :empty-values="[null, undefined]" aria-label="目标文件夹" class="library-select" popper-class="library-select-menu" :teleported="true" :disabled="saving"><el-option label="未分类" value="" /><el-option v-for="folder in folders" :key="folder.id" :label="folder.name" :value="folder.id"><OverflowText :text="folder.name" /></el-option></el-select></div>
      </template>
      <template v-else>
        <p class="field-hint">已选 {{ tagIds.length }} 个标签；创建、改名和删除请前往标签管理。</p>
        <el-checkbox-group v-model="tagIds" class="tag-choices quick-tag-options" aria-label="文献标签选择" :disabled="saving"><el-checkbox v-for="tag in tags" :key="tag.id" :value="tag.id">{{ tag.name }}</el-checkbox></el-checkbox-group>
        <p v-if="!tags.length" class="field-hint">暂无可用标签，请在标签管理中创建。</p>
      </template>
    </template>
    <el-button v-if="!selected && !loading" size="small" @click="load()">重试加载分类</el-button>
    <el-button v-if="conflict" size="small" @click="load(true)">载入最新版本并保留选择</el-button>
  </LibraryActionDialog>
</template>
