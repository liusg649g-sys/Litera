<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ReaderPanel from './ReaderPanel.vue'
import { textHasUnmappedCharacters, unreliableTextMessage } from '../reader/textQuality'
import { createTranslation, type TranslationResult } from '../reader/translation'
import { readerContext, subscribeReaderContext } from '../reader/context'
import { readerTabs } from '../reader/state'
import { auth } from '../auth'
import { api } from '../api'
import {readUserModel,modelSettingsEvent,type UserModelProfile} from '../userModels'
import { translationMatchesSelection, type NoteCaptureDraft } from '../notes/captures'
const model = createTranslation((source,direction,signal,modelSource,modelRevision) => api<TranslationResult>(`/documents/${encodeURIComponent(source.documentId)}/translations`, {method:'POST',signal,body:JSON.stringify({text:source.text,pageNumber:source.pageNumber,contextRevision:source.contextRevision,...(modelSource==='user'?{modelSource,modelRevision}:modelSource==='mock'?{modelSource}:{}),sourceLanguage:direction.split('-')[0],targetLanguage:direction.split('-')[1]})},auth.csrfToken))
const state=model.state, copied=ref('')
const userModelAvailable=ref(false),userProfile=ref<UserModelProfile|null>(null)
const modelOptions=ref({mockEnabled:false,userEnabled:false,developerEnabled:true,defaultSource:'developer' as 'developer'|'user'|'mock',unifiedAcceptance:false})
let modelReadEpoch=0,choiceOwner=''
function preferenceKey(owner:string){return 'litera:translation-model:'+owner}
async function loadUserModel(){
 const token=++modelReadEpoch,owner=auth.user?.id;if(!owner)return
 try{
  const [status,options]=await Promise.all([readUserModel(),api<typeof modelOptions.value>('/user-model/options')])
  if(token!==modelReadEpoch || owner!==auth.user?.id)return
  userModelAvailable.value=status.available;userProfile.value=status.profile;modelOptions.value=options
  if(choiceOwner!==owner){
   choiceOwner=owner
   let preferred='';try{preferred=sessionStorage.getItem(preferenceKey(owner))||''}catch{/* preference only, never credentials */}
   const allowed=preferred==='mock'?options.mockEnabled:preferred==='user'?options.userEnabled:preferred==='developer'?options.developerEnabled:false
   model.setModel(allowed?preferred as 'developer'|'user'|'mock':options.defaultSource,status.profile?.revision||'')
  }else if(state.modelSource==='user')model.setModel('user',status.profile?.revision||'')
 }catch{/* Older APIs preserve their existing developer/isolated Mock behavior. */}
}
function changeModel(event:Event){
 const element=event.target as HTMLSelectElement,source=element.value as 'developer'|'user'|'mock'
 if(source==='developer' && state.modelSource!=='developer' && !window.confirm('后端默认模型可能消耗开发者额度。请确认你已获得使用授权。')){element.value=state.modelSource;return}
 model.setModel(source,source==='user'?userProfile.value?.revision||'':'')
 if(auth.user)try{sessionStorage.setItem(preferenceKey(auth.user.id),source)}catch{/* no credential storage */}
}
const isolatedMockPreview=import.meta.env.VITE_LITERA_PREVIEW_MOCK==='true'
const emit=defineEmits<{ 'update:open': [boolean]; 'save-to-note': [NoteCaptureDraft] }>()
watch(()=>state.open,open=>emit('update:open',open))
const textIssue=computed(()=>state.source?.textExtractionIssue || (textHasUnmappedCharacters(state.source?.text || '') ? unreliableTextMessage : ''))
const resultCurrent=computed(()=>!!state.result && translationMatchesSelection(state.result,state.resultPositions,readerContext.value,state.direction) && ((state.result.modelConfiguration?.source||'developer')===state.modelSource && (state.modelSource!=='user' || state.result.modelConfiguration?.revision===state.modelRevision)))
function saveToNote() {
  const result=state.result
  if(!result?.translationProof)return
  const current=resultCurrent.value
  const draft:NoteCaptureDraft={title:documentTitle(result.source.documentId),source:{
    kind:'translation_excerpt',documentId:result.source.documentId,pageNumber:result.source.pageNumber,
    originalText:result.originalText,translatedText:result.translatedText,
    positions:JSON.parse(JSON.stringify(state.resultPositions)),contextRevision:result.source.contextRevision,
    sourceLanguage:result.source.sourceLanguage as 'en'|'zh',targetLanguage:result.source.targetLanguage as 'en'|'zh',
    translationProof:JSON.parse(JSON.stringify(result.translationProof)),
    ...(result.modelInputText ? {modelInputText:result.modelInputText,normalizationCount:result.normalizationCount}:{}),
    historical:!current,confirmHistorical:false,
  }}
  emit('save-to-note',draft)
}

watch(()=>state.result,()=>{copied.value=''})
// Resolve by each source ID, so switching tabs never labels a result with another document.
function documentTitle(id:string) {
  const title=readerTabs.find(tab=>tab.id===id)?.title.trim()
  return title && title !== '正在读取文献…' ? title : '未命名文献'
}
const stop=subscribeReaderContext((_event,value)=>model.context(value))
watch(()=>auth.user?.id,()=>{modelReadEpoch++;choiceOwner='';model.dispose();userModelAvailable.value=false;userProfile.value=null;void loadUserModel()})
function pointer(event:PointerEvent) {if((event.target as Element)?.closest?.('.pdf-viewport')) model.drag(true)}
function release(){if(state.dragging) model.drag(false)}
onMounted(()=>{void loadUserModel();window.addEventListener(modelSettingsEvent,loadUserModel);window.addEventListener('focus',loadUserModel);model.context(readerContext.value);document.addEventListener('pointerdown',pointer,true);document.addEventListener('pointerup',release,true);document.addEventListener('pointercancel',release,true)})
onBeforeUnmount(()=>{modelReadEpoch++;window.removeEventListener(modelSettingsEvent,loadUserModel);window.removeEventListener('focus',loadUserModel);stop();model.dispose();document.removeEventListener('pointerdown',pointer,true);document.removeEventListener('pointerup',release,true);document.removeEventListener('pointercancel',release,true)})
async function copy(){try{await navigator.clipboard.writeText(state.result!.translatedText);copied.value='已复制译文'}catch{copied.value='复制失败，请手动选择译文复制'}}
defineExpose({toggle:()=>model.setOpen(!state.open),translate:()=>model.request(true),busy:computed(()=>state.loading)})
</script>
<template>
  <ReaderPanel panel-class="translation-panel" :open="state.open" side="right" label="文献翻译" :non-modal="true" @close="model.setOpen(false)">
    <section class="translation-content">
      <p v-if="state.modelSource==='mock' || (isolatedMockPreview && !modelOptions.unifiedAcceptance)" class="translation-disclosure">隔离 Mock 测试：不调用外部模型，返回内容不是实际翻译。</p>
      <p v-else class="translation-disclosure">翻译会将选中文本发送到{{ state.modelSource==='user'?'你配置的':'管理员配置的' }}外部模型服务，不是纯本地处理。仅选择你允许发送的内容。</p>
      <template v-if="userModelAvailable || modelOptions.mockEnabled">
       <label>翻译模型<select aria-label="翻译模型" :value="state.modelSource" @change="changeModel"><option v-if="modelOptions.mockEnabled" value="mock">隔离 Mock（不调用外部服务）</option><option v-if="modelOptions.developerEnabled" value="developer">后端默认模型（需授权）</option><option v-if="modelOptions.userEnabled" value="user">我的模型</option></select></label>
       <p v-if="state.modelSource==='mock'" role="status" data-testid="active-model">当前模型：隔离 Mock · 非真实翻译</p>
       <p v-else-if="state.modelSource==='user'" role="status" data-testid="active-model">{{ userProfile?.verified?'当前模型：'+userProfile.model+'（个人配置）':'模型未配置或尚未验证，请先到 AI 模型设置保存并测试。' }}</p>
       <router-link to="/settings/ai">AI 模型设置</router-link>
      </template>
      <label>翻译模式<select aria-label="翻译模式" :value="state.mode" @change="model.setMode(($event.target as HTMLSelectElement).value)"><option value="manual">手动翻译</option><option value="realtime">实时翻译</option></select></label>
      <label>语言方向<select aria-label="语言方向" :value="state.direction" @change="model.setDirection(($event.target as HTMLSelectElement).value)"><option value="en-zh">英译中</option><option value="zh-en">中译英</option></select></label>
      <p v-if="state.source" class="translation-source" data-testid="translation-source">{{ documentTitle(state.source.documentId) }} · PDF 第 {{ state.source.pageNumber }} 页<span v-if="state.source.positions.length>1">（跨 {{ state.source.positions.length }} 页）</span></p>
      <p v-else>请在 PDF 正文选中文字；扫描图片页没有文字层时无法选区翻译，本轮不提供 OCR。</p>
      <h3>原文</h3><div class="translation-text" data-testid="translation-original" :role="textIssue ? 'alert' : undefined">{{ textIssue || state.source?.text || '尚未选择 PDF 文字' }}</div>
      <button type="button" :disabled="!!textIssue || state.loading" @pointerdown.prevent @click="model.request(true)">{{ state.loading ? (state.queued ? '等待中…' : '翻译中…') : '翻译' }}</button>
      <p v-if="state.loading" role="status">{{ state.queued ? '等待上一请求结束，将翻译最新选区…' : '正在翻译…' }}</p>
      <p v-if="state.error && !textIssue" role="alert">{{ state.error }} <button v-if="!textIssue" :disabled="state.loading" @click="model.request(true)">重试翻译</button></p>
      <p v-if="state.autoPaused" role="status" data-testid="translation-auto-paused">实时翻译已暂停，请稍后手动重试。</p>
      <section v-if="state.result" class="translation-output" :class="{'translation-output-previous':!resultCurrent}">
        <h3 data-testid="translation-result-state">{{ resultCurrent ? '当前选区译文' : '上一条译文' }}</h3>
        <p class="translation-source" data-testid="translation-result-source">{{ documentTitle(state.result.source.documentId) }} · PDF 第 {{ state.result.source.pageNumber }} 页 · {{ state.result.source.sourceLanguage==='en' ? '英译中' : '中译英' }}</p>
        <details v-if="!resultCurrent" class="translation-previous-source">
          <summary>查看此译文对应的原文</summary>
          <div class="translation-text" data-testid="translation-result-original">{{ state.result.originalText }}</div>
        </details>
        <details v-if="state.result.modelInputText && state.result.modelInputText!==state.result.originalText" class="translation-normalization"><summary>已按 PDF 换行证据合并断词</summary><p>原始选区与批注定位保留；以下为实际发送模型的文本。</p><div class="translation-text" data-testid="translation-model-input">{{ state.result.modelInputText }}</div></details>
        <div class="translation-text" data-testid="translation-result">{{ state.result.translatedText }}</div>
        <p v-if="state.result.translationProof?.provenance==='isolated_mock'" role="status" data-testid="translation-mock-label">隔离 Mock 测试结果，非真实模型译文。</p>
        <button :disabled="!state.result.translationProof" @pointerdown.prevent @click="saveToNote">保存到笔记</button>
        <p v-if="!state.result.translationProof" class="translation-source">此结果没有可验证的来源回执，请重新翻译后保存。</p><button @click="copy">复制译文</button><p role="status">{{ copied }}</p>
      </section>
    </section>
  </ReaderPanel>
</template>
<style scoped>
.translation-content{padding:12px;display:flex;flex-direction:column;gap:12px;overflow-wrap:anywhere;min-width:0}.translation-content label{display:flex;justify-content:space-between;gap:8px}.translation-content select{max-width:60%;padding:6px}.translation-text{white-space:pre-wrap;user-select:text;line-height:1.7;max-height:36vh;overflow:auto;background:#f7f7f8;padding:10px;border-radius:6px}.translation-disclosure,.translation-source{font-size:12px;color:#666}.translation-content button{padding:7px 10px;cursor:pointer}.translation-content button:disabled{cursor:default;opacity:.6}.translation-output{display:flex;flex-direction:column;gap:10px;border-top:1px solid #ddd;padding-top:12px}.translation-output-previous h3{color:#775c27}.translation-output summary{cursor:pointer;font-size:12px;color:#666}.translation-content h3,.translation-content p{margin:0}.translation-content [role=alert]{color:#9b0000}
@media(min-width:1100px) and (max-width:1499px){.translation-panel{position:absolute;right:0;top:0;bottom:0;z-index:12;box-shadow:-4px 0 16px #0002}}
@media(max-width:1099px){.translation-panel{height:52dvh;max-height:52dvh;width:100%!important;max-width:100%;top:auto;bottom:0;left:0;right:0;border-top:1px solid #ddd;box-shadow:0 -4px 16px #0002}}
</style>
