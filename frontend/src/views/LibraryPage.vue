<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Collection, Clock, Search, PriceTag, Delete, Folder, Fold, Expand, Plus, Document, Close, MoreFilled } from '@element-plus/icons-vue'
import Brand from '../components/Brand.vue'
import WorkspaceTabs from '../components/WorkspaceTabs.vue'
import { readerTabs } from '../reader/state'
import { startPointerResize as drag } from '../resize'
import OverflowText from '../components/OverflowText.vue'
import DocumentInfoPanel from '../components/DocumentInfoPanel.vue'
import LibraryActionDialog from '../components/LibraryActionDialog.vue'
import DocumentClassifyDialog from '../components/DocumentClassifyDialog.vue'
import { auth, logout } from '../auth'
import { api, ApiError } from '../api'
import { clampSidebar, contentUrl, listDocuments, sizeLabel, uploadDocument, listFolders, listTags, writeCategory, removeCategory, trashDocument, restoreDocument, purgeDocument, retryCleanup, getCleanup } from '../library'
import type { DocumentDTO, FolderDTO, TagDTO, LibraryFilters } from '../library'

const router = useRouter(), route = useRoute()
const busy = ref(false), configError = ref('')
const rows = ref<DocumentDTO[]>([]), loading = ref(true), listError = ref('')
const hasLoaded = ref(false), searchPending = ref(false), libraryTotal = ref<number | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined
const page = ref(1), pageSize = ref(20), total = ref(0), sort = ref('createdAt'), order = ref('desc')
const viewportWidth = ref(window.innerWidth), narrow = computed(() => viewportWidth.value < 760)
const collapsed = ref(narrow.value), sidebarWidth = ref(240)
const navigationTooltip = ref('')
let tooltipTimer: ReturnType<typeof setTimeout> | undefined
function showNavTip(id: string) { clearTimeout(tooltipTimer); navigationTooltip.value = collapsed.value ? id : '' }
function hideNavTip(id: string) { clearTimeout(tooltipTimer); tooltipTimer = setTimeout(() => { if (navigationTooltip.value === id) navigationTooltip.value = '' }, 100) }
watch(collapsed, () => { clearTimeout(tooltipTimer); navigationTooltip.value = '' })
const sidebarSize = computed(() => collapsed.value || narrow.value ? 56 : sidebarWidth.value)
const maxUploadBytes = ref(0), uploading = ref(false), fileInput = ref<HTMLInputElement>()
const detailOpen = ref(false), detailWidth = ref(360), panelBusy = ref(false)
const panel = ref<InstanceType<typeof DocumentInfoPanel>>(), panelShell = ref<HTMLElement>(), panelHeading = ref<HTMLElement>()
const detailOverlay = computed(() => viewportWidth.value - sidebarSize.value < 880)
const detailMaxWidth = computed(() => Math.min(520, viewportWidth.value - sidebarSize.value - 560))
const renderedDetailWidth = computed(() => detailOverlay.value ? Math.min(detailWidth.value, viewportWidth.value - 16) : Math.min(detailWidth.value, detailMaxWidth.value))
const modal = computed(() => detailOpen.value && detailOverlay.value)
const notifications = new Set<{ close: () => void }>()
let listRevision = 0, controller: AbortController | null = null, opener: HTMLElement | null = null
const navigation = [{ label: '我的文献', icon: Collection, view: 'documents' }, { label: '最近阅读', icon: Clock, view: 'recent' }, { label: '文献检索', icon: Search, view: 'search' }, { label: '标签管理', icon: PriceTag, view: 'tags' }, { label: '回收站', icon: Delete, view: 'trash' }]
const mode = computed(() => ['recent', 'search', 'tags', 'trash'].includes(String(route.query.view)) ? String(route.query.view) : 'documents')
const folders = ref<FolderDTO[]>([]), tags = ref<TagDTO[]>([]), categoriesReady = ref(false), categoryError = ref('')
const filters = ref<LibraryFilters>({ q: '', folderId: typeof route.query.folderId === 'string' ? route.query.folderId : '', tagIds: [], yearFrom: '', yearTo: '' })
const appliedFilters = ref<LibraryFilters>({ ...filters.value, tagIds: [] })
const emptyState = computed(() => {
  if (mode.value === 'trash') return { title: '回收站为空', text: '移入回收站的文献将显示在这里。', action: '' }
  if (mode.value === 'recent') return { title: '暂无最近阅读记录', text: '打开文献 PDF 后，会在这里显示。', action: '' }
  const query = appliedFilters.value, narrowed = Boolean(query.q.trim() || query.yearFrom || query.yearTo)
  if (!narrowed && query.tagIds.length && !query.folderId) return { title: '该标签下暂无文献', text: '可通过已有文献的“管理标签”操作进行关联。', action: 'back' }
  if (!narrowed && query.folderId && !query.tagIds.length) return { title: '该文件夹下暂无文献', text: '可通过已有文献的“移动到文件夹”操作进行归类。', action: 'back' }
  if (libraryTotal.value === 0 && !query.folderId && !query.tagIds.length) return { title: '还没有导入文献', text: '导入第一篇 PDF，开始整理文献。', action: 'upload' }
  return { title: '没有符合条件的文献', text: '请调整关键词或筛选条件后重试。', action: 'clear' }
})
const emptyTagView = computed(() => hasLoaded.value && !rows.value.length && !listError.value && emptyState.value.action === 'back' && appliedFilters.value.tagIds.length > 0)
const pageTitle = computed(() => filters.value.folderId && mode.value === 'documents' ? folders.value.find(folder => folder.id === filters.value.folderId)?.name || '文件夹文献' : navigation.find(item => item.view === mode.value)?.label || '我的文献')
type Action = { [K in 'folders' | 'tags']: { kind: K; id?: string; remove?: boolean; name: string } }['folders' | 'tags'] | { [K in 'trash' | 'purge']: { kind: K; document: DocumentDTO } }['trash' | 'purge']
const action = ref<Action | null>(null), actionName = ref(''), actionBusy = ref(false), actionError = ref('')
const quickAction = ref<{ id: string; kind: 'move' | 'tags' } | null>(null), quickBusy = ref(false)
async function openQuick(document: DocumentDTO, kind: 'move' | 'tags') {
  if (!await canLeave()) return
  quickAction.value = { id: document.id, kind }
}
async function classified(document: DocumentDTO) {
  quickAction.value = null; panel.value?.sync(document)
  rows.value = rows.value.map(row => row.id === document.id ? document : row)
  notify('success', '分类已保存', document.title)
  await loadCategories(); await loadList()
}
const actionTitle = computed(() => !action.value ? '' : action.value.kind === 'trash' ? '移入回收站' : action.value.kind === 'purge' ? '永久删除文献' : (action.value.remove ? '删除' : action.value.id ? '重命名' : '新建') + (action.value.kind === 'folders' ? '文件夹' : '标签'))
async function loadCategories() {
  categoryError.value = ''
  try { const result = await Promise.all([listFolders(), listTags()]); folders.value = result[0]; tags.value = result[1]; categoriesReady.value = true }
  catch (error) { categoriesReady.value = false; categoryError.value = message(error) }
}
async function navigate(view: string, folderId?: string) {
  await router.push({ path: '/library', query: { ...(view !== 'documents' ? { view } : {}), ...(folderId ? { folderId } : {}) } })
  if (narrow.value) collapsed.value = true
}
function clearFilters() { filters.value = { q: '', folderId: '', tagIds: [], yearFrom: '', yearTo: '' }; changeSort() }
function filterTag(id: string) { filters.value.tagIds = [id]; changeSort() }
async function showAction(value: Action) {
  if (!await canLeave()) return
  action.value = value; actionName.value = 'name' in value ? value.name : ''; actionError.value = ''
}
async function completeAction() {
  const value = action.value
  if (!value || actionBusy.value) return
  actionBusy.value = true; actionError.value = ''
  try {
    if (value.kind === 'folders' || value.kind === 'tags') {
      if (value.remove) await removeCategory(value.kind, value.id!)
      else await writeCategory(value.kind, actionName.value.trim(), value.id)
      await loadCategories()
      if (value.remove) {
        if (value.kind === 'folders' && filters.value.folderId === value.id) filters.value.folderId = ''
        if (value.kind === 'tags') filters.value.tagIds = filters.value.tagIds.filter(id => id !== value.id)
        detailOpen.value = false
      }
    } else {
      if (value.kind === 'trash') { await trashDocument(value.document.id); const index = readerTabs.findIndex(tab => tab.id === value.document.id); if (index >= 0) readerTabs.splice(index, 1) }
      else {
        const job = await purgeDocument(value.document.id)
        if (job && job.status !== 'completed') {
          action.value = null; detailOpen.value = false
          notify(job.status === 'failed' ? 'error' : 'info', job.status === 'failed' ? '清理未完成' : '正在清理', '清理状态已保存，可在回收站查看并重试。')
          await loadList(); return
        }
      }
      detailOpen.value = false
    }
    action.value = null; notify('success', '操作成功', value.kind === 'purge' ? '文献及 PDF 已永久删除' : value.kind === 'trash' ? '文献已移入回收站' : '分类已更新')
    await loadList()
  } catch (error) { actionError.value = message(error) }
  finally { actionBusy.value = false }
}
const rowBusy = ref('')
async function restore(document: DocumentDTO) {
  if (rowBusy.value) return
  rowBusy.value = document.id
  try { await restoreDocument(document.id); notify('success', '恢复成功', document.title); await loadList() }
  catch (error) { notify('error', '恢复失败', message(error), { label: '重试恢复', run: () => restore(document) }) }
  finally { rowBusy.value = '' }
}
async function cleanup(document: DocumentDTO, retry = false) {
  if (!document.cleanupJob || rowBusy.value) return
  rowBusy.value = document.id
  try {
    const job = retry ? await retryCleanup(document.cleanupJob.jobId) : await getCleanup(document.cleanupJob.jobId)
    notify(!job || job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'info', '清理状态', !job || job.status === 'completed' ? '清理已完成' : job.status === 'failed' ? '清理失败，请检查存储权限或文件占用后重试' : '清理尚未完成，稍后可刷新状态或重试')
    await loadList()
  } catch (error) { notify('error', '清理操作失败', message(error)) }
  finally { rowBusy.value = '' }
}
function readDocument(id: string) { return router.push('/reader/' + encodeURIComponent(id)) }
function dateLabel(value: string | null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' }
function message(error: unknown) { return error instanceof Error ? error.message : '操作失败，请重试' }
function notify(type: 'success' | 'warning' | 'error' | 'info', title: string, text: string, action?: { label: string; run: () => void | Promise<void> }) {
  const instance = ElNotification({ type, title, position: 'bottom-right', duration: 5000, showClose: true,
    customClass: 'library-notification',
    message: h('div', [h('p', text), action ? h('button', { class: 'notification-action', onClick: () => { instance.close(); void action.run() } }, action.label) : null]),
    onClose: () => notifications.delete(instance),
  })
  notifications.add(instance)
}
async function loadConfig() {
  configError.value = ''
  try { maxUploadBytes.value = (await api<{ maxUploadBytes: number }>('/library/config')).maxUploadBytes }
  catch (error) { configError.value = message(error); notify('error', '无法读取上传配置', configError.value, { label: '重试上传配置', run: loadConfig }) }
}
async function loadList() {
  cancelSearch()
  const revision = ++listRevision
  controller?.abort(); controller = new AbortController()
  loading.value = true; listError.value = ''
  const query = { ...filters.value, tagIds: [...filters.value.tagIds] }, view = mode.value
  try {
    if (view === 'tags') { loading.value = false; return }
    const result = await listDocuments(page.value, pageSize.value, sort.value, order.value, controller.signal, query, view)
    if (revision !== listRevision) return
    let actualTotal = libraryTotal.value
    if ((view === 'documents' || view === 'search') && !result.items.length && result.total === 0) {
      // Existing unfiltered API distinguishes a genuinely empty active library
      // from an empty query. Do not infer this from filtered result length.
      const constrained = Object.values(query).some(value => Array.isArray(value) ? value.length : value.trim())
      actualTotal = constrained ? (await listDocuments(1, 1, 'createdAt', 'desc', controller.signal)).total : result.total
    }
    if (revision !== listRevision) return
    rows.value = result.items; total.value = result.total; appliedFilters.value = query; libraryTotal.value = actualTotal; hasLoaded.value = true
    if (!result.items.length && result.total && page.value > 1) { page.value = Math.ceil(result.total / pageSize.value); await loadList() }
  } catch (error) { if (revision === listRevision) { rows.value = []; listError.value = message(error) } }
  finally { if (revision === listRevision) loading.value = false }
}
function cancelSearch() { clearTimeout(searchTimer); searchTimer = undefined; searchPending.value = false }
function scheduleSearch() {
  cancelSearch(); ++listRevision; controller?.abort(); page.value = 1
  if (mode.value === 'tags' || mode.value === 'trash') return
  searchPending.value = true
  if (hasLoaded.value) loading.value = false
  searchTimer = setTimeout(() => { searchTimer = undefined; void loadList() }, 300)
}
watch(() => [filters.value.q, filters.value.folderId, filters.value.tagIds.join(','), filters.value.yearFrom, filters.value.yearTo], scheduleSearch, { flush: 'sync' })
function changeSort() { page.value = 1; void loadList() }
function changeSize() { page.value = 1; void loadList() }
async function signOut() {
  if (busy.value || !await canLeave()) return
  busy.value = true
  try { await logout(); await router.replace('/login') }
  catch (error) { notify('error', '退出失败', message(error), { label: '重试退出', run: signOut }) }
  finally { busy.value = false }
}
function windowResize() {
  viewportWidth.value = window.innerWidth
  if (narrow.value) collapsed.value = true
  if (modal.value) void nextTick(() => {
    if (!panelShell.value?.contains(document.activeElement) && !document.activeElement?.closest('.el-message-box,.el-dialog')) panelHeading.value?.focus()
  })
}
function resizeStart(event: PointerEvent) { if (!collapsed.value && !narrow.value) drag(event, sidebarWidth.value, width => { sidebarWidth.value = clampSidebar(width) }) }
function resizeKey(event: KeyboardEvent) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault(); sidebarWidth.value = clampSidebar(sidebarWidth.value + (event.key === 'ArrowRight' ? 10 : -10))
}
function updateDetailWidth(width: number) { detailWidth.value = Math.max(320, Math.min(detailMaxWidth.value, width)) }
function detailResizeStart(event: PointerEvent) { if (!detailOverlay.value) drag(event, renderedDetailWidth.value, updateDetailWidth, -1) }
function detailResizeKey(event: KeyboardEvent) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault(); updateDetailWidth(renderedDetailWidth.value + (event.key === 'ArrowLeft' ? 10 : -10))
}
function chooseFile() { fileInput.value?.click() }
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (file) await importPdf(file)
}
async function importPdf(file: File) {
  if (uploading.value) return
  const reselect = { label: '重新选择 PDF', run: chooseFile }
  if (!maxUploadBytes.value) { notify('error', '暂时无法导入', '尚未读取上传配置', { label: '重试上传配置', run: loadConfig }); return }
  if (!file.name.toLowerCase().endsWith('.pdf')) { notify('error', '导入失败', '仅支持本地 PDF 文件', reselect); return }
  if (file.size > maxUploadBytes.value) { notify('error', '导入失败', 'PDF 超过上传大小限制（' + sizeLabel(maxUploadBytes.value) + '）', reselect); return }
  uploading.value = true
  try {
    const document = await uploadDocument(file, mode.value === 'documents' ? filters.value.folderId || undefined : undefined)
    notify('success', '导入成功', '已导入「' + document.title + '」', { label: '查看文献', run: () => openDetail(document.id) })
    page.value = 1; await loadList()
  } catch (error) {
    if (error instanceof ApiError && error.code === 'DUPLICATE_DOCUMENT') {
      const id = typeof error.details?.existingDocumentId === 'string' ? error.details.existingDocumentId : ''
      notify('warning', '重复文献', message(error), id ? error.details?.inTrash ? { label: '查看回收站', run: () => navigate('trash') } : { label: '查看已有文献', run: () => openDetail(id) } : reselect)
    } else {
      const retryable = error instanceof ApiError && (error.status === 0 || error.status >= 500)
      notify('error', '导入失败', message(error), retryable ? { label: '重试上传', run: () => importPdf(file) } : reselect)
    }
  } finally { uploading.value = false }
}
async function openDetail(id: string, edit = false) {
  if (!detailOpen.value) { opener = document.activeElement as HTMLElement; detailOpen.value = true; await nextTick() }
  const opened = await panel.value?.open(id, edit)
  if (opened) { await nextTick(); panelHeading.value?.focus() }
}
async function canLeave() { return !auth.user || (!quickBusy.value && (!panel.value || await panel.value.allowLeave())) }
async function closeDetail() {
  if (!await canLeave()) return
  detailOpen.value = false; panelBusy.value = false
  await nextTick()
  if (opener?.isConnected && !opener.closest('.el-notification,.library-popover')) opener.focus()
  else fileInput.value?.parentElement?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()
}
async function saved(document: DocumentDTO) {
  const tab = readerTabs.find(item => item.id === document.id); if (tab) tab.title = document.title
  rows.value = rows.value.map(row => row.id === document.id ? document : row)
  notify('success', '题录已保存', document.title)
  await loadList()
}
function more(command: unknown, document: DocumentDTO) {
  if (command === 'edit') void openDetail(document.id, true)
  if (command === 'move' || command === 'tags') void openQuick(document, command)
  if (command === 'trash') void showAction({ kind: 'trash', document })
}
function panelKeys(event: KeyboardEvent) {
  if (!detailOpen.value || (event.target as HTMLElement).closest('.el-message-box')) return
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); void closeDetail(); return }
  if (!modal.value || event.key !== 'Tab') return
  const focusable = Array.from(panelShell.value?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),[tabindex="0"]') || []).filter(element => element.getClientRects().length)
  const first = focusable[0], last = focusable[focusable.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panelHeading.value)) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
watch(() => [route.query.view, route.query.folderId], () => {
  cancelSearch(); quickAction.value = null; detailOpen.value = false; page.value = 1; hasLoaded.value = false; rows.value = []
  filters.value = { q: '', folderId: typeof route.query.folderId === 'string' ? route.query.folderId : '', tagIds: [], yearFrom: '', yearTo: '' }
  void loadList()
})
onMounted(() => {
  void loadConfig(); void loadCategories(); void loadList(); window.addEventListener('resize', windowResize)
  if (typeof route.query.documentId === 'string') void openDetail(route.query.documentId)
})
onUnmounted(() => { clearTimeout(tooltipTimer); cancelSearch(); ++listRevision; controller?.abort(); notifications.forEach(notification => notification.close()); window.removeEventListener('resize', windowResize) })
</script>
<template>
  <div class="library-workspace">
    <header class="workspace-header library-header" :inert="modal"><Brand /><div class="account-actions"><span class="account-name">{{ auth.user?.displayName }}</span><router-link to="/profile">个人资料</router-link><el-button :loading="busy" size="small" @click="signOut">退出登录</el-button></div></header>
    <WorkspaceTabs :inert="modal" />
    <div class="library-body">
      <button v-if="narrow && !collapsed" class="sidebar-backdrop" aria-label="收起导航" @click="collapsed = true" />
      <aside class="library-sidebar" :inert="modal" :class="{ collapsed, 'sidebar-overlay': narrow && !collapsed }" :style="{ width: (collapsed ? 56 : sidebarWidth) + 'px' }" aria-label="文献库导航">
        <div class="sidebar-heading"><span v-if="!collapsed">文献管理</span><button class="icon-button" :aria-label="collapsed ? '展开导航' : '收起导航'" :aria-expanded="!collapsed" @click="collapsed = !collapsed"><component :is="collapsed ? Expand : Fold" /></button></div>
        <nav><el-tooltip v-for="item in navigation" :key="item.view" :content="item.label" :disabled="!collapsed" :visible="collapsed && navigationTooltip === item.view" :hide-after="100" effect="light" popper-class="library-popover" placement="right"><button class="nav-item" @mouseenter="showNavTip(item.view)" @mouseleave="hideNavTip(item.view)" @focus="showNavTip(item.view)" @blur="hideNavTip(item.view)" :class="{ active: mode === item.view && !filters.folderId }" :aria-label="item.label" :aria-current="mode === item.view && !filters.folderId ? 'page' : undefined" @click="navigate(item.view)"><component :is="item.icon" /><span v-if="!collapsed">{{ item.label }}</span></button></el-tooltip></nav>
        <div v-if="collapsed && folders.length" class="collapsed-folder-divider" role="separator" aria-label="个人文件夹分隔线" />
        <div class="folder-heading" v-if="!collapsed"><span>个人文件夹</span><button class="icon-button" aria-label="新建文件夹" :disabled="!categoriesReady" @click="showAction({ kind: 'folders', name: '' })"><Plus /></button></div>
        <p v-if="categoryError" class="category-state" role="alert">{{ categoryError }}<el-button size="small" @click="loadCategories">重试分类</el-button></p>
        <p v-else-if="!categoriesReady && !collapsed" class="category-state">正在加载分类…</p>
        <p v-else-if="!folders.length && !collapsed" class="category-state">暂无文件夹</p>
        <div v-for="folder in folders" :key="folder.id" class="folder-row"><el-tooltip :content="folder.name" effect="light" :disabled="!collapsed" :visible="collapsed && navigationTooltip === folder.id" :hide-after="100" placement="right" popper-class="library-popover"><button class="nav-item" @mouseenter="showNavTip(folder.id)" @mouseleave="hideNavTip(folder.id)" @focus="showNavTip(folder.id)" @blur="hideNavTip(folder.id)" :class="{ active: mode === 'documents' && filters.folderId === folder.id }" :aria-label="'文件夹：' + folder.name" @click="navigate('documents', folder.id)"><Folder /><OverflowText v-if="!collapsed" :text="folder.name" /></button></el-tooltip>
          <el-dropdown v-if="!collapsed" trigger="click" popper-class="library-popover library-menu" @command="showAction({ kind: 'folders', id: folder.id, name: folder.name, remove: $event === 'delete' })"><button class="icon-button" :aria-label="'管理文件夹：' + folder.name"><MoreFilled /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="rename">重命名文件夹</el-dropdown-item><el-dropdown-item command="delete">删除文件夹</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
        </div>
      </aside>
      <div v-if="!collapsed && !narrow" class="sidebar-resizer" :inert="modal" role="separator" aria-label="调整导航宽度" aria-orientation="vertical" tabindex="0" :aria-valuenow="sidebarWidth" :aria-valuemin="180" :aria-valuemax="320" @pointerdown="resizeStart" @keydown="resizeKey" />
      <main class="library-main" :inert="modal">
        <div v-if="mode !== 'tags' && mode !== 'trash'" v-show="!emptyTagView" class="library-toolbar"><div class="import-actions"><el-button type="primary" :loading="uploading" :disabled="!maxUploadBytes || (Boolean(filters.folderId) && !categoriesReady)" @click="chooseFile"><Plus class="button-icon" />{{ uploading ? '正在导入' : '导入 PDF' }}</el-button><input ref="fileInput" class="sr-only" type="file" accept=".pdf,application/pdf" aria-label="选择本地 PDF" :disabled="uploading" @change="importFile"><span class="upload-hint">本地 PDF<span v-if="maxUploadBytes"> · 上限 {{ sizeLabel(maxUploadBytes) }}</span></span><el-button v-if="configError" size="small" @click="loadConfig">重试上传配置</el-button></div></div>
        <div class="list-heading"><div><h1>{{ pageTitle }}</h1><p>{{ mode === 'trash' ? '恢复可保留题录、分类与 PDF；永久删除不可撤销。' : mode === 'recent' ? '按最近打开 PDF 的时间排序。' : mode === 'tags' ? '用标签组织个人文献。删除标签不会删除文献。' : '管理原始 PDF，整理你的科研积累。' }}</p></div><div class="sort-controls"><template v-if="mode !== 'trash' && mode !== 'tags' && mode !== 'recent'"><label>排序<el-select v-model="sort" class="library-select sort-field" aria-label="排序字段" popper-class="library-select-menu" :teleported="true" @change="changeSort"><el-option label="导入时间" value="createdAt" /><el-option label="标题" value="title" /><el-option label="年份" value="year" /><el-option label="最近阅读" value="lastReadAt" /></el-select></label><el-select v-model="order" class="library-select sort-direction" aria-label="排序方向" popper-class="library-select-menu" :teleported="true" @change="changeSort"><el-option label="降序" value="desc" /><el-option label="升序" value="asc" /></el-select></template><el-button :disabled="loading" @click="mode === 'tags' ? loadCategories() : loadList()">刷新</el-button><el-button v-if="mode === 'tags'" type="primary" :disabled="!categoriesReady" @click="showAction({ kind: 'tags', name: '' })">新建标签</el-button></div></div>
        <form v-if="mode !== 'trash' && mode !== 'tags'" class="library-filters" aria-label="文献检索与筛选" @submit.prevent="changeSort">
          <input v-model="filters.q" type="search" maxlength="500" aria-label="检索关键词" placeholder="搜索标题、作者、摘要或 DOI">
          <el-select v-model="filters.folderId" :empty-values="[null, undefined]" class="library-select folder-filter" aria-label="筛选文件夹" popper-class="library-select-menu" :teleported="true" :disabled="!categoriesReady"><el-option label="全部文件夹" value="" /><el-option v-for="folder in folders" :key="folder.id" :label="folder.name" :value="folder.id"><OverflowText :text="folder.name" /></el-option></el-select>
          <el-dropdown trigger="click" :hide-on-click="false" popper-class="library-popover library-menu" :disabled="!categoriesReady"><el-button>标签筛选{{ filters.tagIds.length ? ' (' + filters.tagIds.length + ')' : '' }}</el-button><template #dropdown><div class="tag-filter-options"><label v-for="tag in tags" :key="tag.id"><input v-model="filters.tagIds" type="checkbox" :value="tag.id">{{ tag.name }}</label><span v-if="!tags.length">暂无标签</span><small>所选标签全部匹配</small></div></template></el-dropdown>
          <input v-model="filters.yearFrom" class="year-filter" inputmode="numeric" maxlength="4" aria-label="起始年份" placeholder="起始年份"><span>–</span><input v-model="filters.yearTo" class="year-filter" inputmode="numeric" maxlength="4" aria-label="结束年份" placeholder="结束年份">
          <el-button type="primary" native-type="submit">检索</el-button><el-button @click="clearFilters">清除筛选</el-button><span class="search-status" role="status" aria-live="polite">{{ searchPending || (loading && hasLoaded) ? '正在检索…' : '' }}</span>
        </form>
        <section v-if="mode === 'tags'" class="tag-management" aria-label="标签管理">
          <p v-if="categoryError" role="alert">{{ categoryError }}<el-button @click="loadCategories">重试加载标签</el-button></p><p v-else-if="!categoriesReady" role="status">正在加载标签…</p><p v-else-if="!tags.length" class="list-state">暂无标签，创建第一个标签开始整理文献。</p>
          <div v-for="tag in tags" v-else :key="tag.id" class="tag-management-row"><OverflowText :text="tag.name" /><div><el-button size="small" @click="navigate('search').then(() => filterTag(tag.id))">查看文献</el-button><el-button size="small" @click="showAction({ kind: 'tags', id: tag.id, name: tag.name })">重命名</el-button><el-button size="small" @click="showAction({ kind: 'tags', id: tag.id, name: tag.name, remove: true })">删除标签</el-button></div></div>
        </section>
        <section v-if="mode !== 'tags'" class="document-list" aria-label="文献列表" :aria-busy="loading || searchPending">
          <div v-if="loading && !hasLoaded" class="list-state" role="status">正在加载文献…</div>
          <div v-else-if="listError" class="list-state"><p role="alert">{{ listError }}</p><el-button @click="loadList">重试加载</el-button></div>
          <div v-else-if="!rows.length" class="list-state empty-state"><Document class="empty-icon" /><h2>{{ emptyState.title }}</h2><p>{{ emptyState.text }}</p><el-button v-if="emptyState.action === 'clear'" @click="clearFilters">清除筛选条件</el-button><el-button v-else-if="emptyState.action === 'back'" @click="navigate('documents').then(clearFilters)">返回我的文献</el-button><el-button v-else-if="emptyState.action === 'upload'" type="primary" :disabled="!maxUploadBytes || uploading" @click="chooseFile">导入第一篇 PDF</el-button></div>
          <div v-else-if="mode === 'trash'" class="table-scroll trash-table"><table><thead><tr><th>原文标题</th><th>所属文件夹</th><th>删除时间</th><th>清理状态</th><th>操作</th></tr></thead><tbody><tr v-for="document in rows" :key="document.id"><td><OverflowText :text="document.title"><Document /></OverflowText></td><td><OverflowText :text="folders.find(folder => folder.id === document.folderId)?.name || '未分类'" /></td><td><OverflowText :text="dateLabel(document.deletedAt)" /></td><td><OverflowText :text="document.cleanupJob ? ({ pending: '等待清理', running: '清理中', failed: '清理失败', completed: '清理完成' })[document.cleanupJob.status] : '可恢复'" /></td><td><div class="row-actions"><template v-if="!document.cleanupJob"><button :disabled="Boolean(rowBusy)" @click="restore(document)">恢复</button><button @click="showAction({ kind: 'purge', document })">永久删除</button></template><template v-else><button :disabled="Boolean(rowBusy)" @click="cleanup(document)">查看状态</button><button :disabled="Boolean(rowBusy)" @click="cleanup(document, true)">重试清理</button></template></div></td></tr></tbody></table></div>
          <div v-else class="table-scroll"><table><thead><tr><th>原文标题</th><th>作者</th><th>发表年份</th><th>期刊</th><th>标签</th><th>操作</th></tr></thead><tbody><tr v-for="document in rows" :key="document.id"><td><OverflowText :text="document.title" as="button" @click="readDocument(document.id)"><Document /></OverflowText></td><td><OverflowText :text="document.authors.join('、') || '—'" /></td><td><OverflowText :text="String(document.year ?? '—')" /></td><td><OverflowText :text="document.journal || '—'" /></td><td><div v-if="document.tags.length" class="table-tags"><el-tooltip v-for="tag in document.tags" :key="tag.id" :content="tag.name" effect="light" popper-class="library-popover"><button @click="filterTag(tag.id)">{{ tag.name }}</button></el-tooltip></div><span v-else class="empty-value">—</span></td><td><div class="row-actions"><button @click="openDetail(document.id)">详情</button><el-tooltip content="下载原始 PDF" effect="light" popper-class="library-popover" :hide-after="100"><a :href="contentUrl(document.id, true)" aria-label="下载原始 PDF">下载</a></el-tooltip><el-dropdown trigger="click" placement="bottom-end" popper-class="library-popover library-menu" :teleported="true" @command="more($event, document)"><button class="more-button" :aria-label="'更多操作：' + document.title"><MoreFilled /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="edit">编辑题录信息</el-dropdown-item><el-dropdown-item command="move">移动到文件夹</el-dropdown-item><el-dropdown-item command="tags">管理标签</el-dropdown-item><el-dropdown-item command="trash" divided>移入回收站</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></td></tr></tbody></table></div>
        </section>
        <div v-if="!listError && mode !== 'tags'" class="library-pagination"><span>共 {{ total }} 篇</span><el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" :pager-count="5" :disabled="loading" @current-change="loadList" /><el-select v-model="pageSize" class="library-select page-size" aria-label="每页数量" popper-class="library-select-menu" :teleported="true" @change="changeSize"><el-option label="20 篇 / 页" :value="20" /><el-option label="50 篇 / 页" :value="50" /><el-option label="100 篇 / 页" :value="100" /></el-select></div>
      </main>
      <template v-if="detailOpen">
        <button v-if="detailOverlay" class="info-backdrop" aria-label="关闭文献信息背景" :disabled="panelBusy" @click="closeDetail" />
        <div v-else class="info-resizer" role="separator" aria-label="调整信息面板宽度" aria-orientation="vertical" tabindex="0" :aria-valuenow="renderedDetailWidth" :aria-valuemin="320" :aria-valuemax="detailMaxWidth" @pointerdown="detailResizeStart" @keydown="detailResizeKey" />
        <aside ref="panelShell" class="document-info-panel" :class="{ 'info-overlay': detailOverlay }" :style="{ width: renderedDetailWidth + 'px' }" :role="detailOverlay ? 'dialog' : 'complementary'" :aria-modal="detailOverlay ? true : undefined" aria-labelledby="document-info-heading" @keydown="panelKeys">
          <div class="info-panel-header"><h2 id="document-info-heading" ref="panelHeading" tabindex="-1">文献信息</h2><button class="icon-button" aria-label="关闭文献信息" :disabled="panelBusy" @click="closeDetail"><Close /></button></div>
          <DocumentInfoPanel ref="panel" :folders="folders" :tags="tags" :categories-ready="categoriesReady" @read="readDocument" @saved="saved" @busy="panelBusy = $event" />
        </aside>
      </template>
    </div>
    <DocumentClassifyDialog v-if="quickAction" :key="quickAction.id + quickAction.kind" :document-id="quickAction.id" :kind="quickAction.kind" @close="!quickBusy && (quickAction = null)" @saved="classified" @busy="quickBusy = $event" />
    <LibraryActionDialog v-if="action" :title="actionTitle" :busy="actionBusy" :error="actionError" :confirm="action.kind === 'purge' ? '永久删除' : action.kind === 'trash' ? '移入回收站' : action.remove ? '删除' : '保存'" @close="!actionBusy && (action = null)" @confirm="completeAction">
      <template v-if="action.kind === 'folders' || action.kind === 'tags'"><p v-if="action.remove">删除「{{ action.name }}」？{{ action.kind === 'folders' ? '文献将转为未分类，PDF 和题录保留。' : '文献保留，仅移除标签关联。' }}</p><form v-else @submit.prevent="completeAction"><label class="category-name-label">{{ action.kind === 'folders' ? '文件夹名称' : '标签名称' }}<input v-model="actionName" maxlength="100" :disabled="actionBusy" required aria-label="分类名称"></label><p class="field-hint">1–100 个字符，同一用户下名称不能重复。</p></form></template>
      <p v-else>确认{{ action.kind === 'purge' ? '永久删除' : '移入回收站' }}「{{ action.document.title }}」？{{ action.kind === 'purge' ? 'PDF 及关联数据将被清理，此操作不可撤销。' : '可在回收站中恢复。' }}</p>
    </LibraryActionDialog>
  </div>
</template>
