<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { ArrowLeft, ArrowRight, ArrowDown, Download, Fold, Expand, Search, ChatLineSquare, EditPen, Brush, Picture, CirclePlus, Crop, RefreshLeft, RefreshRight, Delete, Document, MoreFilled } from '@element-plus/icons-vue'
import Brand from '../components/Brand.vue'
import WorkspaceTabs from '../components/WorkspaceTabs.vue'
import PdfPage from '../components/PdfPage.vue'
import ReaderPanel from '../components/ReaderPanel.vue'
import PdfThumbnail from '../components/PdfThumbnail.vue'
import PdfOutline from '../components/PdfOutline.vue'
import type { OutlineNode } from '../components/PdfOutline.vue'
import PdfSearch from '../components/PdfSearch.vue'
import AnnotationList from '../components/AnnotationList.vue'
import SignaturePad from '../components/SignaturePad.vue'
import ReaderAssetManager from '../components/ReaderAssetManager.vue'
import { bounds, drawingTypes } from '../reader/objectGeometry'
import { uploadAsset, discardAsset, type ReaderAsset } from '../reader/assets'
import AnnotationToolIcon from '../components/AnnotationToolIcon.vue'
import { annotationLabels, annotationColors, createAnnotations } from '../reader/annotations'
import type { AnnotationDTO, AnnotationData, AnnotationType } from '../reader/annotations'
import { normalizedToViewport } from '../reader/state'
import type { SearchMatch } from '../reader/search'
import { createProgress } from '../reader/progress'
import type { ReadingState } from '../reader/progress'
import { clampZoom, fitZoom, PAGE_PADDING, PAGE_GAP } from '../reader/zoom'
import { publishContext, readSelection, readerContext } from '../reader/context'
import { api } from '../api'
import { CORNER_NOTICE_DURATION } from '../notifications'
import { auth } from '../auth'
import { contentUrl } from '../library'
import type { DocumentDTO } from '../library'
import { readerTabs, openReaderTab, clearReaderTabs, pageGroup, adjacentPage } from '../reader/state'
import type { ViewMode, ZoomMode } from '../reader/state'
import { createPdfTask, pdfError, pdfStatus } from '../reader/pdf'
import '../reader/reader.css'
const route = useRoute(), router = useRouter()
const pdf = shallowRef<PDFDocumentProxy>(), viewport = ref<HTMLElement>()
const keyboardFocus = ref(false)
const loading = ref(true), failure = ref(''), count = ref(0), pageInput = ref('1')
const active = computed(() => readerTabs.find(item => item.id === String(route.params.documentId)))
const current = computed(() => active.value?.page || 1)
const mode = computed(() => active.value?.mode || 'continuous')
const scale = computed(() => active.value?.zoom || 1), zoomInput = ref('100')
const sizes = shallowRef<{ width: number; height: number }[]>([])
const outline = shallowRef<OutlineNode[]>([]), outlineError = ref('')
const matches = shallowRef<SearchMatch[]>([]), selectedMatch = ref('')
const matchesByPage = computed(() => { const map = new Map<number, SearchMatch[]>(); for (const match of matches.value) { const list = map.get(match.pageNumber) || []; list.push(match); map.set(match.pageNumber, list) } return map })
const progress = shallowRef<ReturnType<typeof createProgress>>()
const annotations = shallowRef<ReturnType<typeof createAnnotations>>()
const showSaved = ref(false)
let savedTimer: ReturnType<typeof setTimeout> | undefined
const showAnnotationNotice = ref(false)
let annotationNoticeTimer: ReturnType<typeof setTimeout> | undefined
function showCornerNotice() {
  clearTimeout(annotationNoticeTimer)
  showAnnotationNotice.value = !!pdf.value && !!(annotations.value?.state.dirty || annotations.value?.state.hasBackup)
  if (showAnnotationNotice.value) annotationNoticeTimer = setTimeout(() => { showAnnotationNotice.value = false }, CORNER_NOTICE_DURATION)
}
watch([() => annotations.value, () => annotations.value?.state.phase, () => annotations.value?.state.dirty, () => annotations.value?.state.hasBackup, () => !!pdf.value], showCornerNotice)
watch(() => annotations.value?.state.phase, (phase, previous) => {
  clearTimeout(savedTimer); showSaved.value = phase === 'confirmed' && ['sending','draft'].includes(previous || '')
  if (showSaved.value) savedTimer = setTimeout(() => { showSaved.value = false }, 1000)
})
onBeforeUnmount(() => { clearTimeout(savedTimer); clearTimeout(annotationNoticeTimer) })
const annotationTool = ref<AnnotationType | 'erase' | ''>(''), annotationColor = ref('#F5D547'), selectedAnnotation = ref('')
const drawingWidth=ref(2),drawingOpacity=ref(1),placement=ref<ReaderAsset|null>(null),signatureOpen=ref(false),assetBusy=ref(false),assetError=ref('')
const assetManagerOpen=ref(false)
const editorAssets=new Set<string>()
let assetUploadController:AbortController|undefined,inkInitialized=false,colorCustomized=false
const assetFile=ref<HTMLInputElement>(),importType=ref<'image'|'signature'>('image'),retryFile=shallowRef<Blob|null>(null)
function cancelPlacement(){assetUploadController?.abort();assetUploadController=undefined;assetBusy.value=false;retryFile.value=null;assetError.value='';signatureOpen.value=false;annotationTool.value='';const asset=placement.value;placement.value=null;if(asset)void discardAsset(String(route.params.documentId),asset.assetId).then(result=>{if(result)notice.value='图片清理尚未完成，可在资产管理重试。'}).catch(()=>{notice.value='图片清理失败，已登记并将自动重试，也可在资产管理重试。'})}
async function importAsset(file:Blob,type:'image'|'signature'){
  if(assetBusy.value)return
  const id=String(route.params.documentId),controller=new AbortController();assetUploadController=controller;let timedOut=false;const timeout=setTimeout(()=>{timedOut=true;controller.abort()},30000);assetBusy.value=true;assetError.value='';retryFile.value=file;importType.value=type
  try{const asset=await uploadAsset(id,file,controller.signal);if(String(route.params.documentId)!==id){void discardAsset(id,asset.assetId);return}if(editor.value && ['image','signature'].includes(editor.value.type)){
      const physical=await pdf.value!.getPage(editor.value.pageNumber),g=editor.value.geometry
      if(g.kind!=='box')return
      const w=physical.view[2]!-physical.view[0]!,h=physical.view[3]!-physical.view[1]!,ratio=asset.width/asset.height
      const width=Math.min(g.rect.width,(1-g.rect.y)*h/w*ratio),geometry={...g,rect:{...g.rect,width,height:width*w/h/ratio}}
      if(editorSubmitted.value && !annotations.value?.replaceFailedAsset(editor.value.id,asset.assetId,geometry)){void discardAsset(id,asset.assetId);assetError.value='请先核对原保存命令；仅资产失效的确定失败可更换图片后重试。';return}
      editorAssets.add(asset.assetId);const original=editor.value.assetId;editor.value={...editor.value,assetId:asset.assetId,geometry}
      if(original && editorNew.value)void discardAsset(id,original).catch(()=>{})
    }else{placement.value=asset;signatureOpen.value=false;annotationTool.value=type}
    retryFile.value=null}
  catch(error:any){if(!controller.signal.aborted || timedOut)assetError.value=timedOut?'图片上传超时，文件已保留，可重试上传。':error.message || '上传失败，请重试'}finally{clearTimeout(timeout);if(assetUploadController===controller){assetBusy.value=false;assetUploadController=undefined}}
}
function pickAsset(type:'image'|'signature'){importType.value=type;assetFile.value?.click()}
function fileChosen(event:Event){const input=event.target as HTMLInputElement,file=input.files?.[0];if(file)void importAsset(file,importType.value);input.value=''}
function drawingCreated(type:AnnotationType,geometry:AnnotationData['geometry']){
  if(editor.value || assetBusy.value)return
  const data=newAnnotation(type,geometry);data.style={...data.style,lineWidth:drawingWidth.value,opacity:type==='watermark'?.25:drawingOpacity.value,fontSize:type==='watermark'?30:14};data.color=annotationColor.value
  if(type==='watermark')data.content='水印'
  if(['image','signature'].includes(type)){if(!placement.value)return;data.assetId=placement.value.assetId;editorAssets.add(data.assetId);placement.value=null}
  if(type==='ink'){annotations.value?.create(data);selectedAnnotation.value=''}else{annotationTool.value='';setEditor(data,true,false)}
}
const editor = ref<AnnotationDTO | null>(null), editorNew = ref(false)
const editorDialog = ref<HTMLDialogElement>()
let annotationDraftRetained = false
const editorBusy = ref(false), editorSubmitted = ref(false), editorReverting = ref(false)
function editingBlocked() { if (!editor.value && !assetBusy.value && !placement.value && !signatureOpen.value && !retryFile.value) return false; notice.value = '请先 ✓ 保存或 × 取消当前批注编辑。'; return true }
function setEditor(data: AnnotationDTO, isNew = false, navigate = true) {
  if (editingBlocked()) return
  editorAssets.clear();if(isNew && data.assetId)editorAssets.add(data.assetId)
  editorNew.value = isNew; editorSubmitted.value = false; editorReverting.value=false; editor.value = JSON.parse(JSON.stringify(data)); selectedAnnotation.value = data.id
  if (data.type==='comment') { rightPanel.value='批注列表'; rightOpen.value=true }
  else if (data.type==='freeText') { if(window.innerWidth<1100) rightOpen.value=false; if(!isNew && navigate) void navigateAnnotation(data) }
}
function updateEditor(data: AnnotationDTO) { if (!editorSubmitted.value && editor.value?.id===data.id && data.documentId===String(route.params.documentId)) editor.value=data }
function moveAnnotation(id: string, geometry: AnnotationDTO['geometry']) {
  if (editor.value) { if (editor.value.id===id && !editorSubmitted.value) editor.value={...editor.value,geometry}; return }
  annotations.value?.edit(id,{geometry})
}
function removeAnnotation(id: string) { if (!editingBlocked()) annotations.value?.remove(id) }
function closeRight() { if (!editingBlocked()) rightOpen.value=false }
watch(editor, async value => { await nextTick(); if (value && !['comment','freeText',...drawingTypes].includes(value.type) && !editorDialog.value?.open) editorDialog.value?.showModal(); else if ((!value || ['comment','freeText',...drawingTypes].includes(value.type)) && editorDialog.value?.open) editorDialog.value.close() })
watch([() => annotations.value?.state.phase,editorBusy], () => { if(editorSubmitted.value && !editorBusy.value && annotations.value?.state.phase==='confirmed' && !annotations.value.state.dirty) { editorAssets.clear();editor.value=null; editorSubmitted.value=false; selectedAnnotation.value='' } })
const selectedObject = computed(() => annotations.value?.state.items.find(a => a.id === selectedAnnotation.value))
const typeForLabel = (label: string) => (Object.keys(annotationLabels) as AnnotationType[]).find(key => annotationLabels[key] === label)
function newAnnotation(type: AnnotationType, geometry: AnnotationData['geometry'], selectedText: string | null = null): AnnotationDTO {
  const now = new Date().toISOString()
  return { id: crypto.randomUUID(), documentId: String(route.params.documentId), type, schemaVersion: 1, pageNumber: geometry.kind === 'text' ? geometry.positions[0]!.pageNumber : geometry.pageNumber, geometry, position: geometry.kind === 'text' ? geometry.positions : null, selectedText, content: null, color: annotationColor.value, style: { opacity: type === 'highlight' ? .35 : 1, fontSize: 14, lineWidth: 1 }, zIndex: 0, assetId: null, version: 0, createdAt: now, updatedAt: now }
}
async function createFromSelection(type: AnnotationType) {
  const document = pdf.value, root = viewport.value, token = generation
  if (!document || !root) return false
  const selected = { documentId: String(route.params.documentId), ...await readSelection(document, root).catch(() => ({ selectedText: '', selectionPosition: null })) }
  if (token !== generation) return false
  if (!selected?.selectionPosition?.length || selected.documentId !== String(route.params.documentId) || !selected.selectedText) return false
  const data = newAnnotation(type, { kind: 'text', positions: JSON.parse(JSON.stringify(selected.selectionPosition)) }, selected.selectedText)
  if (type === 'comment') setEditor(data,true)
  else { annotations.value?.create(data); selectedAnnotation.value = '' }
  window.getSelection()?.removeAllRanges(); annotationTool.value = ''; return true
}
function chooseTool(label: string) {
  if (editingBlocked()) return
  const type = typeForLabel(label)
  if (!type) { pending(label); return }
  if (!pdf.value || annotations.value?.state.phase === 'loading') return
  selectedAnnotation.value = ''; annotationTool.value = type
  if(type==='ink' && !inkInitialized){inkInitialized=true;if(!colorCustomized)annotationColor.value='#9B0000'}
  if(type==='image'){annotationTool.value='';pickAsset('image');return}
  if(type==='signature'){annotationTool.value='';signatureOpen.value=true;return}
  if (!drawingTypes.includes(type) && type !== 'freeText') createFromSelection(type)
}
async function selectionFinished(event: PointerEvent) {
  if (group.value !== '批注' || editor.value) return
  if ((event.target as Element).closest('.annotation-hit')) return
  const type = annotationTool.value
  if (type && type !== 'erase' && type !== 'freeText' && !drawingTypes.includes(type)) createFromSelection(type)
}
function placeAnnotation(pageNumber: number, x: number, y: number) {
  if (editingBlocked()) return
  const type = annotationTool.value
  if (type !== 'comment' && type !== 'freeText') return
  const geometry: AnnotationData['geometry'] = type === 'comment' ? { kind: 'anchor', pageNumber, x, y } : { kind: 'box', pageNumber, rotation: 0, rect: { x: Math.min(.98,x), y: Math.min(.98,y), width: Math.min(.32,1-Math.min(.98,x)), height: Math.min(.12,1-Math.min(.98,y)) } }
  setEditor(newAnnotation(type,geometry),true); annotationTool.value = ''
}
async function openEditor(item: AnnotationDTO, navigate = true) {
  if (editor.value) { editingBlocked(); return }
  const targetGroup=['rectangle','circle','ellipse'].includes(item.type)?'形状':['image','signature','watermark'].includes(item.type)?'插入':'批注'
  if ((drawingTypes.includes(item.type) || item.type==='freeText') && group.value!==targetGroup) { group.value=targetGroup; await nextTick() }
  annotationTool.value=''
  setEditor(item,false,navigate)
}
async function cancelEditor() {
  if (editorBusy.value) return
  const manager=annotations.value
  if (editorSubmitted.value && manager) {
    editorBusy.value=true
    try {
      if (manager.state.error) await manager.retry(); else await manager.flush()
      if (manager.state.error || manager.state.dirty) { notice.value='取消需先确认已提交命令，请恢复网络重试；冲突请通过错误栏核对。'; return }
      if (!editorReverting.value) { editorReverting.value=true; await manager.undo() }
      if (manager.state.error || manager.state.dirty) return
    } finally { editorBusy.value=false }
  }
  if(editor.value && !editorSubmitted.value)for(const assetId of editorAssets)void discardAsset(editor.value.documentId,assetId).catch(()=>{notice.value='未引用图片已登记，稍后自动清理；可从资产管理重试。'})
  editorAssets.clear()
  editor.value=null; editorSubmitted.value=false; editorReverting.value=false; selectedAnnotation.value=''
}
async function saveEditor() {
  if (editorReverting.value) { await cancelEditor(); return }
  if (!editor.value || editorBusy.value) return
  const data = editor.value, manager = annotations.value
  if (!manager || (['comment','freeText','watermark'].includes(data.type) && !data.content?.trim())) return
  editorBusy.value=true
  try {
    if (!editorSubmitted.value) {
      if (editorNew.value) manager.create(data)
      else manager.edit(data.id, { content: data.content, color: data.color, style: data.style, ...(data.geometry.kind==='text' ? {} : { geometry: data.geometry }) })
      editorSubmitted.value=true
    }
    if (manager.state.error) await manager.retry(); else await manager.flush()
    if (!manager.state.dirty && !manager.state.error && annotations.value===manager) { editorAssets.clear();selectedAnnotation.value=''; editor.value=null; editorSubmitted.value=false }
  } finally { editorBusy.value=false }
}
function selectAnnotation(item: AnnotationDTO) {
  if (editor.value?.id===item.id) return
  if (editor.value && editor.value.id!==item.id) { editingBlocked(); return }
  if (group.value !== '阅读' && annotationTool.value==='erase') { annotations.value?.remove(item.id); return }
  selectedAnnotation.value = item.id; if (group.value==='阅读' || (!drawingTypes.includes(item.type) && item.type!=='freeText')) { rightPanel.value = '批注列表'; rightOpen.value = true }

}
async function navigateAnnotation(item: AnnotationDTO) {
  if (editor.value && editor.value.id!==item.id) { editingBlocked(); return }
  selectedAnnotation.value = item.id; jump(item.pageNumber)
  const token = generation, page = await pdf.value?.getPage(item.pageNumber)
  if (!page || token!==generation) return
  const r = bounds(item.geometry)
  navigation = { page: item.pageNumber, annotationId: item.id, point: normalizedToViewport(page.getViewport({scale:scale.value}),r.x,r.y) }; await nextTick(); await locate()
}
function changeColor(color: string) { colorCustomized=true;annotationColor.value=color; if(editor.value) { if(!editorSubmitted.value) editor.value={...editor.value,color}; return }; if (selectedObject.value) annotations.value?.edit(selectedObject.value.id,{ color }) }
async function reloadAnnotations() {
  try { await annotations.value?.reloadServer(); editor.value=null; editorSubmitted.value=false; selectedAnnotation.value = ''; showCornerNotice(); notice.value = '已载入服务端批注并清空撤销历史，保留的本地草稿可导出。' }
  catch { notice.value = '无法核对服务端批注，本地草稿仍保留，请稍后重试。' }
}
async function retainDraftAndReturn() {
  if (editor.value && !editorSubmitted.value) { editingBlocked(); return }; if (await annotations.value?.preserveForLeave()) { editor.value=null; annotationDraftRetained = true; await router.push('/library') }
}
async function annotationKeys(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (editor.value && event.key==='Escape' && !target.closest('input,textarea,select')) { event.preventDefault(); cancelEditor(); return }
  if (editor.value || target.isContentEditable || target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="dialog"]') || !target.closest('.reader-workspace')) return
  if (event.key === 'Escape') { cancelPlacement(); selectedAnnotation.value = ''; annotationTool.value = ''; return }
  if ((event.ctrlKey || event.metaKey) && ['z','y'].includes(event.key.toLowerCase())) { event.preventDefault(); if (event.key.toLowerCase()==='y' || event.shiftKey) await annotations.value?.redo(); else await annotations.value?.undo() }
  else if (['Delete','Backspace'].includes(event.key) && viewport.value?.contains(target) && selectedObject.value) { event.preventDefault(); annotations.value?.remove(selectedObject.value.id) }
}
const pages = computed(() => pageGroup(current.value, count.value, mode.value))
const leftOpen = ref(false), rightOpen = ref(false), rightPanel = ref('搜索')
const leftPanel = ref('缩略图'), group = ref('阅读'), notice = ref('')
const leftWidth = ref(240)
const tools = {
  '批注': [['高亮', EditPen], ['下划线', EditPen], ['波浪线', EditPen], ['删除线', EditPen], ['注释', ChatLineSquare], ['自由文本', Document], ['手绘', Brush]],
  '形状': [['矩形', Crop], ['圆形', CirclePlus], ['椭圆形', CirclePlus]],
  '插入': [['签名', EditPen], ['水印', Document], ['图片', Picture]],
} as const
const activeTools = computed(() => group.value === '阅读' ? [] : tools[group.value as keyof typeof tools])
let generation = 0, resource: ReturnType<typeof createPdfTask> | undefined
let metadataRequest: AbortController | undefined
let scrollFrame = 0, leaving = false, fullFallback = false
let layoutFrame = 0, layoutRevision = 0, suppressScroll = false
let resizeObserver: ResizeObserver | undefined, fitRevision = 0, selectionRevision = 0, anchorRevision = 0
const ready = ref(false)
let navigating = false, jumpRevision = 0, loadedDocumentId = ''
function readingState(): ReadingState { return { pageNumber: current.value, zoom: scale.value, zoomMode: active.value?.zoomMode || 'fit-width', viewMode: mode.value } }
function context(event: 'context-change' | 'document-change' | 'selection-change' = 'context-change') {
  publishContext(event, { documentId: String(route.params.documentId), pageNumber: current.value, selectedText: '', selectionPosition: null })
}
function pageReady(number: number) {
  if (number !== current.value || loadedDocumentId !== String(route.params.documentId)) return
  ready.value = true; void progress.value?.ready(readingState())
  if (navigation) void locate()
}
async function beforeLeave() {
  if (!auth.user) return true
  if (editor.value || placement.value || signatureOpen.value || assetBusy.value || retryFile.value) { notice.value = '请先保存或取消当前创建/编辑，再离开。'; return false }
  await annotations.value?.flush(); await progress.value?.flush()
  if (annotations.value?.state.dirty && !annotationDraftRetained) { notice.value = '批注尚未保存，请重试、导出草稿或明确保留草稿后离开。'; return false }
  return !progress.value?.status.dirty || (!!failure.value && !pdf.value)
}
onBeforeRouteLeave(beforeLeave)
onBeforeRouteUpdate(beforeLeave)
watch([group, leftOpen, rightOpen, leftWidth, notice, () => progress.value?.status.error], async () => {
  const root = viewport.value, token = generation, revision = ++layoutRevision, page = current.value, navigationRevision = jumpRevision
  if (!root || !pdf.value) return
  const node = root.querySelector<HTMLElement>(`[data-page="${page}"]`)
  const offset = node ? node.getBoundingClientRect().top - root.getBoundingClientRect().top : 0
  const scrollLeft = root.scrollLeft
  suppressScroll = true; cancelAnimationFrame(scrollFrame); cancelAnimationFrame(layoutFrame)
  await nextTick()
  if (revision !== layoutRevision || token !== generation || leaving) return
  if (page !== current.value || navigationRevision !== jumpRevision) { suppressScroll = false; return }
  if (node?.isConnected) root.scrollTop += node.getBoundingClientRect().top - root.getBoundingClientRect().top - offset
  root.scrollLeft = scrollLeft
  if (active.value) active.value.page = page
  pageInput.value = String(page)
  layoutFrame = requestAnimationFrame(() => { suppressScroll = false })
})
function anchor(x?: number, y?: number) {
  const root = viewport.value
  if (!root) return () => {}
  const bounds = root.getBoundingClientRect(), sx = x ?? bounds.left + root.clientWidth / 2, sy = y ?? bounds.top + root.clientHeight / 2
  const nodes = [...root.querySelectorAll<HTMLElement>('[data-page]')]
  const node = nodes.find(el => { const r = el.getBoundingClientRect(); return r.left <= sx && sx <= r.right && r.top <= sy && sy <= r.bottom }) || nodes.find(el => Number(el.dataset.page) === current.value)
  if (!node) return () => {}
  const rect = node.getBoundingClientRect(), px = (sx - rect.left) / rect.width, py = (sy - rect.top) / rect.height, number = Number(node.dataset.page)
  return () => {
    const target = root.querySelector<HTMLElement>(`[data-page="${number}"]`)
    if (!target) return
    const rect = target.getBoundingClientRect()
    root.scrollLeft += rect.left + rect.width * px - sx; root.scrollTop += rect.top + rect.height * py - sy
  }
}
async function applyScale(value: number, zoomMode: ZoomMode, x?: number, y?: number) {
  if (!active.value || !pdf.value || loadedDocumentId !== String(route.params.documentId)) return
  const restore = navigating ? () => {} : anchor(x, y), token = generation, revision = ++anchorRevision, page = current.value, navigationRevision = jumpRevision
  suppressScroll = true; active.value.zoomMode = zoomMode; active.value.zoom = clampZoom(value)
  zoomInput.value = String(Math.round(active.value.zoom * 10000) / 100)
  window.getSelection()?.removeAllRanges()
  await nextTick()
  if (token !== generation || revision !== anchorRevision) return
  if (navigationRevision !== jumpRevision) { suppressScroll = false; return }
  restore(); active.value!.page = page; pageInput.value = String(page)
  cancelAnimationFrame(layoutFrame); layoutFrame = requestAnimationFrame(() => { suppressScroll = false })
}
function zoom(value: number, x?: number, y?: number) { if (Number.isFinite(value)) void applyScale(value, 'custom', x, y) }
watch(scale, value => { zoomInput.value = String(Math.round(value * 10000) / 100) })
function manualZoom() {
  const raw = zoomInput.value.trim().replace(/%$/, '')
  if (!raw || !Number.isFinite(Number(raw))) { notice.value = '请输入有效的缩放比例'; return }
  const value = Number(raw) / 100
  if (value < .5 || value > 5) notice.value = '缩放范围为 50%–500%，已调整到边界'
  zoom(value)
}
function fit(value?: ZoomMode) {
  const zoomMode = value || active.value?.zoomMode
  if (!pdf.value || loadedDocumentId !== String(route.params.documentId) || !viewport.value || !active.value || !zoomMode || zoomMode === 'custom') return
  const numbers = mode.value === 'spread' ? pageGroup(current.value, count.value, 'spread') : [current.value]
  const selected = numbers.map(n => sizes.value[n - 1]!).filter(Boolean)
  if (!selected.length) return
  const root = viewport.value, next = fitZoom(selected, root.clientWidth, root.clientHeight, zoomMode)
  if (Math.abs(next - scale.value) > .0001 || active.value.zoomMode !== zoomMode) void applyScale(next, zoomMode)
}
function wheel(event: WheelEvent) {
  if (!event.ctrlKey || !pdf.value) return
  event.preventDefault(); zoom(scale.value * Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * .002), event.clientX, event.clientY)
}
watch([current, mode], ([, value], [, previous]) => {
  if (!pdf.value || loadedDocumentId !== String(route.params.documentId)) return
  const selected = readerContext.value
  if (value !== previous) { window.getSelection()?.removeAllRanges(); context() }
  else if (selected?.selectedText) publishContext('context-change', { documentId: selected.documentId, pageNumber: selected.pageNumber, selectedText: selected.selectedText, selectionPosition: selected.selectionPosition })
  else context()
  // Native multi-page selection must survive auto-scroll across mixed page sizes.
  if (value === previous && mode.value === 'continuous' && window.getSelection()?.isCollapsed === false) return
  fit()
})
watch([current, mode, scale, () => active.value?.zoomMode], () => { if (ready.value && pdf.value && loadedDocumentId === String(route.params.documentId)) progress.value?.stage(readingState()) })
async function selectionChanged() {
  const token = generation, revision = ++selectionRevision, document = pdf.value, root = viewport.value
  if (!document || !root) return
  const selection = await readSelection(document, root).catch(() => ({ selectedText: '', selectionPosition: null }))
  if (token !== generation || revision !== selectionRevision || leaving) return
  const old = readerContext.value
  const pageNumber = selection.selectionPosition?.[0]?.pageNumber || current.value
  if (old?.selectedText === selection.selectedText && old?.pageNumber === pageNumber && JSON.stringify(old.selectionPosition) === JSON.stringify(selection.selectionPosition)) return
  publishContext('selection-change', { documentId: String(route.params.documentId), pageNumber, ...selection })
}
async function resolveProgress(local: boolean) {
  try {
    const value = await progress.value?.resolve(local)
    if (value && active.value) { active.value.zoomMode = value.zoomMode; active.value.zoom = value.zoom || 1; active.value.mode = value.viewMode; jump(value.pageNumber || 1); fit(); await nextTick(); progress.value?.stage(readingState()); await progress.value?.flush() }
  } catch { notice.value = '无法读取最新阅读记录，请稍后重试'; }
}
function pending(name: string) { notice.value = `${name}功能开发中，本阶段不会创建或保存批注数据。` }
watch(group, value => { assetManagerOpen.value=false;selectedAnnotation.value = ''; annotationTool.value = ''; if (value === '阅读') {cancelPlacement();notice.value = ''} })
function openRight(name: string) { if (editor.value && name!=='批注列表') { editingBlocked(); return }; rightPanel.value = name; rightOpen.value = true }
async function load(full = false) {
  const token = ++generation, id = String(route.params.documentId)
  suppressScroll = false; layoutRevision++; cancelAnimationFrame(layoutFrame)
  group.value = '阅读';assetManagerOpen.value=false;assetError.value='';retryFile.value=null
  metadataRequest?.abort(); metadataRequest = new AbortController()
  const signal = metadataRequest.signal
  const old = resource; resource = undefined
  progress.value?.dispose(); progress.value = createProgress(id); const saving = progress.value
  annotations.value?.dispose(); annotations.value = createAnnotations(id); const marking = annotations.value
  annotationDraftRetained = false
  annotationTool.value = ''; selectedAnnotation.value = ''; editor.value = null
  ready.value = false; loadedDocumentId = ''; navigation = undefined; fitRevision++; selectionRevision++
  sizes.value = []; outline.value = []; outlineError.value = ''; matches.value = []; selectedMatch.value = ''
  pdf.value = undefined; count.value = 0; loading.value = true; failure.value = ''; notice.value = ''
  window.getSelection()?.removeAllRanges()
  context('document-change')
  await nextTick() // Unmount/cancel page render tasks before document destruction.
  await old?.destroy().catch(() => {})
  if (leaving || token !== generation) return
  const tab = openReaderTab(id)
  let owned: ReturnType<typeof createPdfTask> | undefined
  try {
    const doc = await api<DocumentDTO>(`/documents/${encodeURIComponent(id)}`, { signal })
    const saved = await saving.load(signal)
    await marking.load()
    if (token !== generation || leaving) return
    tab.title = doc.title
    owned = createPdfTask(contentUrl(id), full); resource = owned
    const loaded = await owned.promise
    if (token !== generation || leaving) { await owned.destroy(); return }
    const dimensions: { width: number; height: number }[] = []
    for (let start = 1; start <= loaded.numPages; start += 2) {
      const batch = await Promise.all(Array.from({ length: Math.min(2, loaded.numPages - start + 1) }, async (_, offset) => { const page = await loaded.getPage(start + offset); const v = page.getViewport({ scale: 1 }); return { width: v.width, height: v.height } }))
      if (token !== generation || leaving) return
      dimensions.push(...batch)
    }
    sizes.value = dimensions
    count.value = loaded.numPages; tab.page = Math.min(Math.max(1, saved.pageNumber || 1), loaded.numPages)
    tab.mode = saved.viewMode; tab.zoom = clampZoom(saved.zoom || 1); tab.zoomMode = saved.zoomMode
    zoomInput.value = String(Math.round(tab.zoom * 10000) / 100)
    pageInput.value = String(tab.page); loadedDocumentId = id; pdf.value = loaded; loading.value = false
    void loaded.getOutline().then(value => { if (token === generation) outline.value = (value || []) as OutlineNode[] }).catch(() => { if (token === generation) outlineError.value = '无法读取 PDF 大纲' })
    await nextTick()
    if (token !== generation || leaving) return
    fit(); await nextTick(); jump(tab.page); context('document-change')
  } catch (error) {
    if (token !== generation || leaving) { await owned?.destroy().catch(() => {}); return }
    if (pdfStatus(error) === 416 && !full) { fullFallback = true; void load(true); return }
    await fail(error)
  }
}
async function fail(error: unknown) {
  if (pdfStatus(error) === 416 && !fullFallback) { fullFallback = true; void load(true); return }
  failure.value = pdfError(error); loading.value = false; pdf.value = undefined
  if (pdfStatus(error) === 401) window.dispatchEvent(new Event('litera:unauthenticated'))
  const old = resource; resource = undefined
  await nextTick(); await old?.destroy().catch(() => {})
}
function jump(value: number) {
  if (!pdf.value || !active.value) return
  if (!Number.isInteger(value) || value < 1 || value > count.value) { notice.value = `请输入 1–${count.value} 的整数页码`; pageInput.value = String(current.value); return }
  const revision = ++jumpRevision, token = generation
  window.getSelection()?.removeAllRanges()
  navigating = true; active.value.page = value; pageInput.value = String(value)
  void nextTick(() => {
    if (token !== generation || revision !== jumpRevision) return
    if (mode.value === 'continuous') {
      const node = viewport.value?.querySelector<HTMLElement>(`[data-page="${value}"]`)
      if (node) viewport.value!.scrollTop += node.getBoundingClientRect().top - viewport.value!.getBoundingClientRect().top - PAGE_PADDING
    } else viewport.value?.scrollTo(0, 0)
    requestAnimationFrame(() => { if (revision === jumpRevision) navigating = false })
  })
}
let navigation: { page: number; match?: SearchMatch; point?: number[]; annotationId?: string } | undefined
async function locate() {
  const target = navigation, root = viewport.value
  if (!target || !root) return
  await nextTick()
  if (navigation !== target) return
  const page = root.querySelector<HTMLElement>(`[data-page="${target.page}"]`)
  if (!page || page.dataset.status !== '已渲染') return
  const mark = target.match ? page.querySelector<HTMLElement>(`[data-match="${target.match.id}"]`) : undefined
  const annotation = target.annotationId ? page.querySelector<SVGGraphicsElement>(`[data-annotation="${CSS.escape(target.annotationId)}"]`) : undefined
  const rect = page.getBoundingClientRect(), bounds = root.getBoundingClientRect()
  if (mark) { const r = mark.getBoundingClientRect(); root.scrollTop += r.top - bounds.top - root.clientHeight / 3; root.scrollLeft += r.left - bounds.left - root.clientWidth / 3 }
  // Anchor points describe the bubble's tail, not its visible top edge. Use the
  // rendered bounds for every annotation so flipped bubbles and text marks share
  // the same page padding without a hard-coded icon-size offset.
  else if (annotation) { const r=annotation.getBoundingClientRect(); root.scrollTop += r.top-bounds.top-PAGE_PADDING; root.scrollLeft += r.left-bounds.left-PAGE_PADDING }
  else if (target.point) { root.scrollTop += rect.top + target.point[1]! - bounds.top - PAGE_PADDING; root.scrollLeft += rect.left + target.point[0]! - bounds.left - PAGE_PADDING }
  navigation = undefined
}
async function navigateMatch(match: SearchMatch) {
  selectedMatch.value = match.id; jump(match.pageNumber); navigation = { page: match.pageNumber, match }; await nextTick(); await locate()
}
async function navigateOutline(item: OutlineNode) {
  const token = generation, document = pdf.value
  if (!document) return
  try {
    if (item.url || !item.dest) throw new Error()
    const destination = typeof item.dest === 'string' ? await document.getDestination(item.dest) : item.dest
    if (!destination || destination.length < 2) throw new Error()
    const type = destination[1]?.name
    if (!['XYZ','Fit','FitB','FitH','FitBH','FitV','FitBV','FitR'].includes(type)) throw new Error()
    if (destination.slice(2).some(value => value !== null && (typeof value !== 'number' || !Number.isFinite(value)))) throw new Error()
    if (type === 'FitR' && (destination.length !== 6 || destination.slice(2).some(value => value === null) || destination[4] <= destination[2] || destination[5] <= destination[3])) throw new Error()
    const number = typeof destination[0] === 'number' ? destination[0] + 1 : await document.getPageIndex(destination[0]) + 1
    if (!Number.isInteger(number) || number < 1 || number > document.numPages) throw new Error()
    const page = await document.getPage(number)
    if (token !== generation) return
    jump(number); await nextTick(); fit(); await nextTick()
    const v = page.getViewport({ scale: scale.value })
    let point = [0, 0]
    if (type === 'XYZ' || type === 'FitH' || type === 'FitBH' || type === 'FitV' || type === 'FitBV' || type === 'FitR') {
      const [x0,, , y1] = v.viewBox
      const x = type === 'XYZ' || type === 'FitR' || type === 'FitV' || type === 'FitBV' ? destination[2] ?? x0 : x0
      const y = type === 'XYZ' ? destination[3] ?? y1 : type === 'FitH' || type === 'FitBH' ? destination[2] ?? y1 : type === 'FitR' ? destination[5] ?? y1 : y1
      point = v.convertToViewportPoint(x, y)
    } else if (type !== 'Fit' && type !== 'FitB') throw new Error()
    navigation = { page: number, point }; await locate()
  } catch { if (token === generation) notice.value = '无法跳转：目录目标无效或不是受支持的文内位置' }
}
function step(direction: number) { jump(adjacentPage(current.value, count.value, mode.value, direction)) }
function changeMode(value: unknown) {
  if (!active.value) return
  const restore = anchor(), token = generation
  active.value.mode = value as ViewMode
  active.value.scrollTop = 0
  window.getSelection()?.removeAllRanges()
  jump(current.value)
  void nextTick(async () => { fit(); await nextTick(); if (token === generation) restore() })
}
function scrolled() {
  cancelAnimationFrame(scrollFrame)
  scrollFrame = requestAnimationFrame(() => {
    if (!active.value || !viewport.value || suppressScroll) return
    active.value.scrollTop = viewport.value.scrollTop
    if (mode.value !== 'continuous' || !pdf.value) return
    const bounds = viewport.value.getBoundingClientRect(), center = bounds.top + bounds.height / 2
    let closest = Infinity, found = current.value
    for (const element of viewport.value.querySelectorAll<HTMLElement>('[data-page]')) {
      const rect = element.getBoundingClientRect()
      const distance = center < rect.top ? rect.top - center : center > rect.bottom ? center - rect.bottom : 0
      if (distance < closest) { closest = distance; found = Number(element.dataset.page) }
    }
    active.value.page = found; pageInput.value = String(found)
  })
}
function keydown(event: KeyboardEvent) {
  if (event.target !== viewport.value || mode.value === 'continuous') return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); step(event.key === 'ArrowLeft' ? -1 : 1) }
}
function tabFocus(event: KeyboardEvent) { if (event.key === 'Tab') keyboardFocus.value = true }
function pointerFocus(event: PointerEvent) { keyboardFocus.value = false; if (!editor.value && !(event.target as Element).closest('.annotation-hit,.free-text-editor,.free-text-controls')) selectedAnnotation.value = '' }
watch(() => route.params.documentId, () => { fullFallback = false; void load() }, { immediate: true })
watch(() => auth.user, (user, previous) => {
  if (!user || user.id !== previous?.id) {
    annotations.value?.dispose(true); editor.value = null; progress.value?.dispose(true); publishContext('context-cleared'); generation++; metadataRequest?.abort(); clearReaderTabs(); pdf.value = undefined; count.value = 0
    loading.value = false; failure.value = '登录身份已变更，请重新打开文献'
    const old = resource; resource = undefined
    void nextTick(() => { void old?.destroy().catch(() => {}) })
  }
})
function beforeUnload(event: BeforeUnloadEvent) { if (progress.value?.status.dirty || annotations.value?.state.dirty || editor.value || placement.value || signatureOpen.value || assetBusy.value || retryFile.value) { void progress.value?.flush(); void annotations.value?.flush(); event.preventDefault(); event.returnValue = '' } }
onMounted(() => {
  viewport.value?.addEventListener('wheel', wheel, { passive: false })
  document.addEventListener('selectionchange', selectionChanged); window.addEventListener('beforeunload', beforeUnload)
  document.addEventListener('keydown', tabFocus, true)
  document.addEventListener('keydown', annotationKeys)
  resizeObserver = new ResizeObserver(() => { const revision = ++fitRevision; requestAnimationFrame(() => { if (revision === fitRevision && !leaving) fit() }) }); if (viewport.value) resizeObserver.observe(viewport.value)
})
onBeforeUnmount(() => {
  leaving = true; generation++; metadataRequest?.abort(); cancelAnimationFrame(scrollFrame); cancelAnimationFrame(layoutFrame)
  window.getSelection()?.removeAllRanges()
  progress.value?.dispose(); publishContext('context-cleared'); resizeObserver?.disconnect(); viewport.value?.removeEventListener('wheel', wheel)
  document.removeEventListener('selectionchange', selectionChanged); window.removeEventListener('beforeunload', beforeUnload)
  document.removeEventListener('keydown', tabFocus, true)
  document.removeEventListener('keydown', annotationKeys); annotations.value?.dispose()
  const old = resource; resource = undefined
  void nextTick(() => { void old?.destroy().catch(() => {}) })
})
</script>
<template>
  <main class="reader-workspace" :style="{ '--reader-page-padding': PAGE_PADDING + 'px', '--reader-page-gap': PAGE_GAP + 'px' }">
    <header class="reader-brandbar"><Brand /><span class="reader-caption">PDF 阅读器</span><nav><router-link to="/library">返回文献库</router-link><router-link to="/profile">{{ auth.user?.displayName }}</router-link></nav></header>
    <WorkspaceTabs />
    <div class="reader-main-toolbar" aria-label="阅读工具栏">
      <button :aria-label="leftOpen ? '收起文献导航' : '展开文献导航'" :aria-expanded="leftOpen" @click="leftOpen = !leftOpen"><component :is="leftOpen ? Fold : Expand" /></button>
      <div class="reader-paging"><button aria-label="上一页" :disabled="!pdf || current === 1" @click="step(-1)"><ArrowLeft /></button>
        <form @submit.prevent="jump(Number(pageInput))"><input v-model="pageInput" aria-label="当前页码" inputmode="numeric" :disabled="!pdf"><span>/ {{ count || '—' }}</span></form>
        <button aria-label="下一页" :disabled="!pdf || (mode === 'spread' ? pageGroup(current, count, mode).at(-1) === count : current === count)" @click="step(1)"><ArrowRight /></button></div>
      <el-select :model-value="mode" aria-label="阅读视图" class="reader-view-select" @update:model-value="changeMode"><el-option label="单页连续滚动" value="continuous" /><el-option label="单页切换" value="single" /><el-option label="双页并排" value="spread" /></el-select>
      <div class="reader-zoom"><button aria-label="缩小" :disabled="!pdf || scale <= .5" @click="zoom(scale - .25)">−</button><form @submit.prevent="manualZoom"><input v-model="zoomInput" aria-label="缩放比例" :disabled="!pdf" inputmode="decimal"><span>%</span></form><button aria-label="放大" :disabled="!pdf || scale >= 5" @click="zoom(scale + .25)">＋</button>
        <el-dropdown trigger="click" @command="(value: string) => value.startsWith('fit') ? fit(value as ZoomMode) : zoom(Number(value))"><button aria-label="缩放预设" :disabled="!pdf"><ArrowDown class="reader-chevron" aria-hidden="true" /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fit-width">适应宽度</el-dropdown-item><el-dropdown-item command="fit-height">适应高度</el-dropdown-item><el-dropdown-item v-for="value in [50,75,100,125,150,200,300,400,500]" :key="value" :command="String(value / 100)">{{ value }}%</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
      </div>
      <div class="reader-groups" aria-label="工具分组"><button v-for="name in ['阅读','批注','形状','插入']" :key="name" :aria-pressed="group === name" :class="{ selected: group === name }" @click="!editingBlocked() && (group = name)">{{ name }}</button></div>
      <div class="reader-actions">
        <el-tooltip content="搜索文献" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="搜索文献" @click="openRight('搜索')"><Search /></button></el-tooltip>
        <el-tooltip content="批注列表" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="批注列表" @click="openRight('批注列表')"><ChatLineSquare /></button></el-tooltip>
        <el-tooltip v-if="pdf" content="下载原始 PDF" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><a :href="contentUrl(String(route.params.documentId), true)" aria-label="下载原始 PDF"><Download /></a></el-tooltip>
        <el-tooltip content="导出功能开发中" effect="light" popper-class="library-popover" :hide-after="100" :show-after="150" :popper-options="{ strategy: 'fixed' }"><button aria-label="导出功能开发中" @click="pending('导出')"><MoreFilled /></button></el-tooltip>
      </div>
    </div>
    <div v-if="group !== '阅读'" class="reader-secondary" :aria-label="`${group}工具栏`"><el-tooltip v-for="tool in activeTools" :key="tool[0]" :content="tool[0]" effect="light" :show-after="250"><button :aria-label="typeForLabel(tool[0]) ? tool[0] : `${tool[0]}（功能开发中）`" :aria-disabled="!typeForLabel(tool[0])" :aria-pressed="!!typeForLabel(tool[0]) && annotationTool === typeForLabel(tool[0])" :class="{ selected: !!typeForLabel(tool[0]) && annotationTool === typeForLabel(tool[0]) }" @mousedown.prevent @click="chooseTool(tool[0])"><AnnotationToolIcon v-if="group==='批注'" :name="tool[0]"/><component v-else :is="tool[1]" /><span>{{ tool[0] }}</span></button></el-tooltip>
      <button v-if="group==='插入'" @click="assetManagerOpen=!assetManagerOpen">资产管理</button><span class="reader-toolbar-rule" /><button v-for="color in annotationColors" :key="color" class="reader-color" :class="{ selected: annotationColor===color }" :style="{ '--swatch': color }" :aria-label="`颜色 ${color}`" @mousedown.prevent @click="changeColor(color)" /><input type="color" :value="annotationColor" aria-label="自定义批注颜色" @input="changeColor(($event.target as HTMLInputElement).value)">
      <button aria-label="选择批注" :aria-pressed="annotationTool === ''" @click="!editingBlocked() && (annotationTool = '', selectedAnnotation = '')">选择</button><button aria-label="撤销批注" :disabled="!annotations?.state.undoCount || !!annotations.state.error" @click="!editingBlocked() && annotations?.undo()"><RefreshLeft /></button><button aria-label="重做批注" :disabled="!annotations?.state.redoCount || !!annotations.state.error" @click="!editingBlocked() && annotations?.redo()"><RefreshRight /></button><button aria-label="橡皮擦" :class="{ selected: annotationTool==='erase' }" :aria-pressed="annotationTool==='erase'" @click="!editingBlocked() && (annotationTool = annotationTool==='erase' ? '' : 'erase')"><Delete /></button><button v-if="selectedObject" aria-label="编辑选中批注" @click="openEditor(selectedObject)">编辑</button><button v-if="selectedObject" aria-label="删除选中批注" @click="removeAnnotation(selectedObject.id)">删除</button><label v-if="annotationTool==='ink' || ['rectangle','circle','ellipse'].includes(annotationTool)">线宽<input v-model.number="drawingWidth" aria-label="画笔线宽" type="number" min="0.25" max="20" step="0.25"></label><label v-if="drawingTypes.includes(annotationTool)">透明度<input v-model.number="drawingOpacity" aria-label="绘制透明度" type="number" min="0.05" max="1" step="0.05"></label><button v-if="placement || signatureOpen" @click="cancelPlacement">× 取消放置</button><span class="reader-stage-hint">{{ annotationTool==='erase' ? '点击批注删除' : drawingTypes.includes(annotationTool) ? (['ink','rectangle','circle','ellipse'].includes(annotationTool)?'按下并拖动绘制 · Esc 取消':'移动鼠标预览 · 点击放置 · Esc 取消') : annotationTool ? '选择文本或点击页面创建' : '选择文本后使用批注工具' }}</span>
    </div>
    <input ref="assetFile" type="file" accept="image/png,image/jpeg" aria-label="选择本地图片" hidden @change="fileChosen">
    <ReaderAssetManager v-if="assetManagerOpen" :document-id="String(route.params.documentId)" :key="String(route.params.documentId)" @close="assetManagerOpen=false" />
    <SignaturePad v-if="signatureOpen" @confirm="importAsset($event,'signature')" @import="pickAsset('signature')" @cancel="cancelPlacement" />
    <div v-if="assetBusy || assetError" class="reader-notice" role="status">{{ assetBusy?'正在安全校验图片…':assetError }}<button v-if="assetError && retryFile" @click="importAsset(retryFile,importType)">重试上传</button><button @click="cancelPlacement">× 取消</button></div>
    <div v-if="annotations && pdf && showAnnotationNotice" class="annotation-save-status" aria-live="polite">{{ annotations.state.phase==='sending' ? '正在保存批注…' : annotations.state.dirty ? '批注有未保存修改' : '草稿备份已保留' }}<button v-if="annotations.state.dirty && !annotations.state.error" @click="annotations.flush">立即保存</button><button v-if="annotations.state.hasBackup" @click="annotations.exportDraft">导出保留草稿</button></div>
    <div v-if="annotations?.state.error" class="reader-notice annotation-error" role="alert">{{ annotations.state.error }}<button v-if="annotations.state.phase!=='conflict'" @click="annotations.retry">重试保存批注</button><button @click="annotations.exportDraft">导出批注草稿</button><button @click="reloadAnnotations">载入服务端批注并保留草稿备份</button><button @click="retainDraftAndReturn">保留批注草稿并返回文献库</button></div>
    <div v-if="notice" class="reader-notice" role="status">{{ notice }}<button aria-label="关闭提示" @click="notice = ''">×</button></div>
    <div v-if="pdf && ready && progress?.status.error" class="reader-notice" role="alert">{{ progress.status.error }}<div v-if="progress.status.conflict"><button @click="resolveProgress(false)">载入服务端进度</button><button @click="resolveProgress(true)">保存本地进度</button></div><button v-else :disabled="progress.status.saving" @click="progress.retry">重试阅读记录</button></div>
    <div class="reader-body">
      <ReaderPanel v-model:width="leftWidth" :resizable="true" :open="leftOpen" side="left" label="文献导航" @close="leftOpen = false"><div class="reader-panel-tabs"><button v-for="name in ['缩略图','大纲']" :key="name" :class="{ selected: leftPanel === name }" @click="leftPanel = name">{{ name }}</button></div><template v-if="pdf && leftOpen"><div v-if="leftPanel === '缩略图'" class="pdf-thumbnails"><PdfThumbnail v-for="number in count" :key="`${route.params.documentId}-${number}`" :pdf="pdf" :page-number="number" :current="current" @navigate="jump" /></div><template v-else><p v-if="outlineError || !outline.length" class="reader-panel-placeholder" role="status">{{ outlineError || '此 PDF 没有内置大纲' }}</p><PdfOutline v-else :key="String(route.params.documentId)" :items="outline" @navigate="navigateOutline" /></template></template></ReaderPanel>
      <div class="pdf-reading-region">
      <div v-if="showSaved" class="annotation-saved-toast" role="status"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#35a568"/><path d="m6.5 12 3.5 3.5 7.5-8" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>批注已保存</div>
      <div ref="viewport" class="pdf-viewport" :class="{ 'keyboard-focus': keyboardFocus }" tabindex="0" aria-label="PDF 阅读区域" :aria-busy="loading" @pointerdown="pointerFocus" @pointerup="selectionFinished" @scroll.passive="scrolled" @keydown="keydown">
        <div v-if="loading" class="reader-status" role="status"><span class="reader-spinner" /><h1>正在加载 PDF</h1><p>正在读取受保护的文献内容…</p></div>
        <div v-else-if="failure" class="reader-status" role="alert"><Document /><h1>无法打开文献</h1><p>{{ failure }}</p><p v-if="progress?.status.dirty">本地未同步阅读设置已保留，恢复文献后可处理。</p><div><el-button @click="fullFallback = false; load()">重试加载</el-button><el-button @click="router.push('/library')">返回文献库</el-button></div></div>
        <div v-else-if="pdf && viewport" class="pdf-pages" :class="mode" :key="String(route.params.documentId)">
          <PdfPage v-for="number in pages" :key="`${String(route.params.documentId)}-${mode}-${number}`" :pdf="pdf" :document-id="String(route.params.documentId)" :drawing-color="annotationColor" :drawing-width="drawingWidth" :drawing-opacity="drawingOpacity" :placement="placement" :page-number="number" :root="viewport" :scale="scale" :size="sizes[number - 1]!" :matches="matchesByPage.get(number) || []" :selected="selectedMatch" :annotations="annotations?.state.items || []" :annotation-editor="editor && (editor.type==='freeText' || drawingTypes.includes(editor.type)) ? editor : null" :editor-locked="editorSubmitted" :editor-busy="editorBusy" :editing-active="!!editor" :selected-annotation="selectedAnnotation" :annotation-tool="group!=='阅读' ? annotationTool : ''" :annotation-enabled="group!=='阅读'" :annotation-group="group" @annotation-draw="drawingCreated" @annotation-warning="notice=$event" @annotation-replace-asset="pickAsset(editor?.type==='signature' ? 'signature' : 'image')" @annotation-select="selectAnnotation" @annotation-place="placeAnnotation" @annotation-move="moveAnnotation" @annotation-edit="item => openEditor(item,false)" @annotation-draft="updateEditor" @annotation-save="saveEditor" @annotation-cancel="cancelEditor" @ready="pageReady" @failure="fail" />
        </div>
      </div>
      </div>
      <ReaderPanel :open="rightOpen" side="right" :label="rightPanel" :fixed-content="rightPanel === '批注列表'" :non-modal="rightPanel==='批注列表'" @close="closeRight"><PdfSearch v-if="pdf" v-show="rightPanel === '搜索'" :key="String(route.params.documentId)" :pdf="pdf" :selected="selectedMatch" @matches="matches = $event; selectedMatch = ''" @navigate="navigateMatch" /><AnnotationList v-if="annotations" v-show="rightPanel === '批注列表'" :items="annotations.state.items" :editor="editor?.type==='comment' ? editor : null" :editor-locked="editorSubmitted" :editor-busy="editorBusy" @draft="updateEditor" @save="saveEditor" @cancel="cancelEditor" :has-backup="annotations.state.hasBackup" :has-pending="annotations.state.dirty && !annotations.state.error" @save-pending="annotations.flush" @export-backup="annotations.exportDraft" :document-id="String(route.params.documentId)" :selected="selectedAnnotation" @select="navigateAnnotation" @edit="openEditor" @remove="removeAnnotation" /></ReaderPanel>
    </div>
    <dialog ref="editorDialog" class="annotation-editor" aria-labelledby="annotation-editor-title" @cancel.prevent="cancelEditor"><header><strong id="annotation-editor-title">{{ editorNew ? '创建批注' : '编辑批注' }}</strong></header>
      <form v-if="editor && !['comment','freeText',...drawingTypes].includes(editor.type)" @submit.prevent="saveEditor"><p>{{ annotationLabels[editor.type] }} · 第 {{ editor.pageNumber }} 页</p><label v-if="['comment','freeText'].includes(editor.type)">正文<textarea v-model="editor.content" aria-label="批注正文" maxlength="20000" rows="4" autofocus required /></label><p v-else class="annotation-editor-quote">{{ editor.selectedText }}</p><div class="annotation-editor-colors" role="group" aria-label="批注颜色选择"><span>颜色</span><button v-for="color in annotationColors" :key="color" type="button" class="reader-color" :style="{ '--swatch': color }" :aria-label="`编辑批注颜色 ${color}`" :aria-pressed="editor.color.toUpperCase()===color" :title="color" @click="editor.color=color" /><label>自定义<input v-model="editor.color" aria-label="编辑批注颜色" type="color"></label></div><label>透明度<input v-model.number="editor.style.opacity" aria-label="批注透明度" type="number" min="0.05" max="1" step="0.05" required></label><label v-if="editor.type==='freeText'">字号 (pt)<input v-model.number="editor.style.fontSize" aria-label="批注字号" type="number" min="6" max="144" required></label><label v-if="['underline','squiggly','strikeout'].includes(editor.type)">线宽 (pt)<input v-model.number="editor.style.lineWidth" aria-label="批注线宽" type="number" min="0.25" max="20" step="0.25" required></label><div class="annotation-editor-actions"><el-button @click="cancelEditor">取消</el-button><el-button type="primary" native-type="submit">保存批注</el-button></div></form>
    </dialog>
  </main>
</template>
