<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import ReaderPanel from './ReaderPanel.vue'
import NoteDocuments from './NoteDocuments.vue'
import NoteSourceBlocks from './NoteSourceBlocks.vue'
import {navigateReader} from '../reader/navigation'
import {reliableSourcePosition} from '../reader/sourceHighlight'
import {readerTabs} from '../reader/state'
import {auth} from '../auth'
import {createNotesController,type NoteSearchMatch,type NoteSummary} from '../notes'
import type {NoteSourceLocation} from '../notes/captures'
const props=defineProps<{documentId:string}>()
const emit=defineEmits<{'update:open':[open:boolean]}>()
let storage:Storage|undefined
try{storage=sessionStorage}catch{/* Blocked browser storage is reported on editing. */}
const model=createNotesController(undefined,storage),state=model.state
const navigationBusy=ref(false),navigationError=ref(''),navigationMessage=ref(''),navigationBlockId=ref('')
let navigationController:AbortController|undefined,navigationTarget='',navigationEpoch=0
const navigationKind=ref<''|'document'|'source'>('')
const supersededTargets=new Set<string>()
function cancelNavigation(clearFeedback=true,supersede=false){
 if(supersede && navigationController && navigationTarget)supersededTargets.add(navigationTarget)
 navigationController?.abort();navigationController=undefined;navigationTarget='';navigationKind.value='';navigationBlockId.value='';navigationEpoch++;navigationBusy.value=false
 if(clearFeedback){navigationError.value='';navigationMessage.value=''}
}
watch(()=>auth.user?.id,id=>{cancelNavigation();void model.setUser(id || '')},{immediate:true})
watch(()=>props.documentId,id=>{
 if(navigationController && id!==navigationTarget && !supersededTargets.has(id))cancelNavigation()
 supersededTargets.delete(id);void model.setDocument(id)
},{immediate:true})
watch(()=>state.open,open=>emit('update:open',open))
const status=computed(()=>!state.editor?'请选择或新建笔记':state.editor.saving?'保存中…':state.editor.conflict?'保存冲突，输入已保留':state.editor.error?'保存失败，输入已保留':state.editor.dirty?'等待自动保存…':'已保存')
const searchActive=computed(()=>!!state.search.input.trim())
const candidates=computed(()=>state.personal.items.filter(note=>!note.documents.some(document=>document.id===state.documentId)))
function matchPart(match:NoteSearchMatch,part:'before'|'hit'|'after'){
 const start=Math.max(0,Math.min(match.snippet.length,match.matchStart)),end=Math.max(start,Math.min(match.snippet.length,match.matchEnd))
 return part==='before'?match.snippet.slice(0,start):part==='hit'?match.snippet.slice(start,end):match.snippet.slice(end)
}
async function openDocument(documentId:string,note:NoteSummary|undefined=state.editor?.note){
 if(!note || state.busy || navigationBusy.value || documentId===props.documentId || !note.documents.some(document=>document.id===documentId))return
 const owner=auth.user?.id,origin=props.documentId,attempt=++navigationEpoch,controller=new AbortController()
 navigationController=controller;navigationTarget=documentId;navigationKind.value='document';navigationBusy.value=true;navigationError.value='';navigationMessage.value=''
 try{
  if(!await model.flush()){navigationError.value='笔记尚未保存，请先重试保存或处理冲突后打开文献。';return}
  if(attempt!==navigationEpoch || owner!==auth.user?.id || props.documentId!==origin)return
  const result=await navigateReader({documentId,pageNumber:readerTabs.find(tab=>tab.id===documentId)?.page || 1},{signal:controller.signal})
  if(attempt!==navigationEpoch || owner!==auth.user?.id)return
  if(result.status!=='ok'){navigationError.value=result.message;return}
  if(props.documentId===documentId && await model.setDocument(documentId) && state.editor?.note.id!==note.id)await model.choose(note.id)
 }catch{if(attempt===navigationEpoch)navigationError.value='无法打开关联文献，请稍后重试。'}
 finally{if(attempt===navigationEpoch){navigationController=undefined;navigationTarget='';navigationKind.value='';navigationBusy.value=false}}
}
async function openSource(block:NoteSourceLocation){
 const note=state.editor?.note,source=block.source
 if(!note || state.busy)return
 if(!source.documentId.trim() || !Number.isInteger(source.pageNumber) || source.pageNumber<1 || !/^[a-f0-9]{64}$/i.test(source.fileSha256 || '')){navigationError.value='无法可靠定位来源：来源文献、PDF 版本或物理页码信息不完整。';navigationMessage.value='';return}
 cancelNavigation(false,true)
 const owner=auth.user?.id,noteId=note.id,target=source.documentId,attempt=++navigationEpoch,controller=new AbortController()
 navigationController=controller;navigationTarget=target;navigationKind.value='source';navigationBlockId.value=block.id;navigationBusy.value=true;navigationError.value='';navigationMessage.value=''
 try{
  if(!await model.flush()){navigationError.value='笔记尚未保存，请先重试保存或处理冲突后查看原文。';return}
  if(attempt!==navigationEpoch || owner!==auth.user?.id)return
  const position=reliableSourcePosition(source.positions,source.pageNumber)
  const result=await navigateReader({documentId:target,pageNumber:source.pageNumber,fileSha256:source.fileSha256,...(position?{position}:{})},{signal:controller.signal})
  if(attempt!==navigationEpoch || owner!==auth.user?.id || controller.signal.aborted)return
  if(result.status!=='ok'){navigationError.value=result.message;return}
  if(props.documentId!==target){navigationError.value='无法可靠定位来源：阅读器未停留在来源文献。';return}
  if(!await model.setDocument(target)){navigationError.value='已打开来源页，但笔记状态未能安全切换；当前草稿仍保留。';return}
  if(state.editor?.note.id!==noteId && !await model.choose(noteId)){navigationError.value='已打开来源页，但无法重新打开原笔记；请从个人笔记中再次选择。';return}
  navigationMessage.value=result.message || (result.precision==='exact'
   ? `已精确定位来源文献 PDF 第 ${source.pageNumber} 页的原文。`
   : `已打开来源文献 PDF 第 ${source.pageNumber} 页；当前来源只能定位到页面。`)
 }catch{if(attempt===navigationEpoch && !controller.signal.aborted)navigationError.value='无法可靠定位来源：导航请求失败，请稍后重试。'}
 finally{if(attempt===navigationEpoch){navigationController=undefined;navigationTarget='';navigationKind.value='';navigationBlockId.value='';navigationBusy.value=false}supersededTargets.delete(target)}
}
async function chooser(){state.chooser=!state.chooser;if(state.chooser)await model.loadPersonal(1)}
async function remove(){const editor=state.editor,documentId=props.documentId;if(!editor || !await model.flush() || state.editor!==editor || state.documentId!==documentId || props.documentId!==documentId)return;if(window.confirm('删除笔记本体及其在所有文献中的关联？这与仅解除当前文献关联不同，删除后无法撤销。'))await model.remove()}
async function reload(){if(window.confirm('载入服务器版本将丢弃此笔记当前未保存的本地草稿。是否继续？'))await model.reload()}
function beforeUnload(event:BeforeUnloadEvent){if(model.hasUnsaved()){event.preventDefault();event.returnValue=''}}
window.addEventListener('beforeunload',beforeUnload)
onBeforeUnmount(()=>{cancelNavigation();window.removeEventListener('beforeunload',beforeUnload);model.dispose()})
defineExpose({currentNote:computed(()=>state.editor?.note || null),prepareForInsert:async()=>state.available && !state.busy && !navigationBusy.value && await model.flush(),afterCapture:model.acceptCapture,toggle:()=>model.setOpen(!state.open),beforeLeave:model.beforeLeave,open:computed(()=>state.open),busy:computed(()=>state.busy || !!state.editor?.saving)})
</script>
<template>
 <ReaderPanel panel-class="notes-panel" :open="state.open" side="right" label="文献笔记" :non-modal="true" @close="model.setOpen(false)">
  <section class="notes-content">
   <p v-if="state.checking" role="status">正在检查笔记服务…</p>
   <p v-else-if="!state.available" role="status" data-testid="notes-unavailable">{{ state.unavailable || '笔记尚未部署，等待数据库升级确认。' }}</p>
   <template v-if="state.available">
    <p v-if="state.success" role="status" data-testid="note-operation-success">{{state.success}}</p>
    <div class="notes-actions"><button :disabled="state.busy || navigationBusy" @click="model.create()">新建笔记</button><button :disabled="state.busy || navigationBusy" @click="chooser">关联已有笔记</button></div>
    <section class="note-search" aria-label="搜索个人笔记">
     <label>搜索个人笔记<input aria-label="搜索个人笔记关键词" type="search" autocomplete="off" maxlength="100" placeholder="搜索标题、正文、原文或译文" :value="state.search.input" @input="model.setSearchInput(($event.target as HTMLInputElement).value)" /></label>
     <button v-if="searchActive" aria-label="清空笔记搜索" @click="model.clearSearch()">清空</button>
     <template v-if="searchActive">
      <p v-if="state.search.loading" role="status" data-testid="note-search-loading">正在搜索笔记…</p>
      <p v-else-if="state.search.error" role="alert" data-testid="note-search-error">搜索失败：{{state.search.error}} <button @click="model.runSearch(state.search.page)">重试</button></p>
      <p v-else-if="!state.search.items.length" role="status" data-testid="note-search-empty">没有找到匹配的已保存笔记。</p>
      <section v-else class="note-search-results" aria-label="笔记搜索结果" data-testid="note-search-results">
       <article v-for="note in state.search.items" :key="note.id" class="note-search-result" :data-note-id="note.id">
        <button :aria-label="`打开搜索结果：${note.title}`" :aria-pressed="state.editor?.note.id===note.id" :disabled="state.busy || navigationBusy" @click="model.choose(note.id)">{{note.title}}</button>
        <p class="search-document-count">关联文献 {{note.documents.length}} 篇</p>
        <p v-for="(match,index) in note.matches" :key="`${note.id}-${index}`" class="search-match" :data-match-field="match.field">
         <span class="match-label">{{match.label}}</span><span v-if="match.pageNumber">PDF 第 {{match.pageNumber}} 页 · </span><span v-if="match.leadingEllipsis">…</span><span>{{matchPart(match,'before')}}</span><mark>{{matchPart(match,'hit')}}</mark><span>{{matchPart(match,'after')}}</span><span v-if="match.trailingEllipsis">…</span>
        </p>
       </article>
       <div v-if="state.search.total>state.search.pageSize" class="notes-actions"><button aria-label="上一页搜索结果" :disabled="state.search.page<=1 || state.search.loading" @click="model.runSearch(state.search.page-1)">上一页</button><span>{{state.search.page}} / {{Math.ceil(state.search.total/state.search.pageSize)}}</span><button aria-label="下一页搜索结果" :disabled="state.search.page*state.search.pageSize>=state.search.total || state.search.loading" @click="model.runSearch(state.search.page+1)">下一页</button></div>
      </section>
     </template>
    </section>
    <p v-if="state.error" role="alert">{{state.success ? '操作已完成，但列表刷新失败：' : ''}}{{ state.error }} <button :disabled="state.busy || navigationBusy" @click="model.refreshList()">重试读取</button></p>
    <p v-if="navigationBusy" role="status">{{navigationKind==='source'?'正在核对并打开笔记来源…':'正在打开关联文献…'}}</p>
     <p v-if="navigationMessage" role="status" data-testid="note-navigation-success">{{navigationMessage}}</p>
    <p v-if="navigationError" role="alert" data-testid="note-navigation-error">{{navigationError}}</p>
    <p v-if="state.backupWarning" role="alert">{{ state.backupWarning }}</p>
    <p v-if="state.loading" role="status">正在读取笔记…</p>
    <section v-if="!searchActive" aria-label="当前文献笔记列表" class="note-list">
     <p v-if="!state.loading && !state.error && !state.list.items.length">当前文献还没有笔记。</p>
     <button v-for="note in state.list.items" :key="note.id" :aria-label="`打开笔记：${note.title}`" :aria-pressed="state.editor?.note.id===note.id" :disabled="state.busy || navigationBusy" @click="model.choose(note.id)">{{ note.title }}</button>
     <div v-if="state.list.total>state.list.pageSize" class="notes-actions"><button aria-label="上一页文献笔记" :disabled="state.list.page<=1 || state.loading" @click="model.refreshList(state.list.page-1)">上一页</button><span>{{state.list.page}} / {{Math.ceil(state.list.total/state.list.pageSize)}}</span><button aria-label="下一页文献笔记" :disabled="state.list.page*state.list.pageSize>=state.list.total || state.loading" @click="model.refreshList(state.list.page+1)">下一页</button></div>
    </section>
    <section v-if="state.chooser" aria-label="个人已有笔记" class="note-picker">
     <h3>个人已有笔记</h3><p>关联会复用同一条笔记，不复制正文。</p>
     <p v-if="!state.busy && !state.error && !candidates.length">此页没有可关联的笔记。</p>
     <article v-for="note in candidates" :key="note.id" class="note-candidate">
      <button :aria-label="`关联笔记：${note.title}`" :disabled="state.busy || navigationBusy" @click="model.link(note.id)">{{note.title}}</button>
      <NoteDocuments :documents="note.documents" :current-document-id="props.documentId" :disabled="state.busy || navigationBusy" :label="`${note.title}的关联文献`" @open-document="openDocument($event,note)" />
     </article>
     <div v-if="state.personal.total>state.personal.pageSize" class="notes-actions"><button aria-label="上一页个人笔记" :disabled="state.personal.page<=1 || state.busy" @click="model.loadPersonal(state.personal.page-1)">上一页</button><span>{{state.personal.page}} / {{Math.ceil(state.personal.total/state.personal.pageSize)}}</span><button aria-label="下一页个人笔记" :disabled="state.personal.page*state.personal.pageSize>=state.personal.total || state.busy" @click="model.loadPersonal(state.personal.page+1)">下一页</button></div>
    </section>
    <section v-if="state.editor" class="note-editor" aria-label="笔记编辑器">
     <label>标题<input aria-label="笔记标题" :value="state.editor.title" :maxlength="state.config.titleMaxLength" :disabled="state.busy || navigationBusy" @input="model.edit('title',($event.target as HTMLInputElement).value)" /></label>
     <label>正文<textarea aria-label="笔记正文" :value="state.editor.content" :maxlength="state.config.contentMaxLength" :disabled="state.busy || navigationBusy" @input="model.edit('content',($event.target as HTMLTextAreaElement).value)" /></label>
     <p role="status" aria-live="polite" data-testid="note-save-status">{{status}}</p>
     <p v-if="state.editor.error" role="alert">{{state.editor.error}}</p>
     <div class="notes-actions"><button v-if="state.editor.error && !state.editor.conflict" :disabled="state.editor.saving || state.busy" @click="model.retrySave()">重试保存</button><button v-else-if="!state.editor.conflict" :disabled="!state.editor.dirty || state.editor.saving || state.busy" @click="model.flush()">立即保存</button><button v-if="state.editor.conflict" :disabled="state.busy || navigationBusy" @click="reload">载入服务器版本</button></div>
     <p class="notes-help">纯文本编辑；停止输入约0.8秒后自动保存。未保存草稿只保留在本账号的当前浏览器会话中。</p>
     <NoteSourceBlocks :sources="state.editor.note.sources" :documents="state.editor.note.documents" :disabled="state.busy" :navigating-id="navigationBlockId" @navigate-source="openSource" />
     <NoteDocuments :documents="state.editor.note.documents" :current-document-id="props.documentId" :disabled="state.busy || navigationBusy" @open-document="openDocument($event)" />
     <p class="notes-help">解除关联仅移除当前文献的关系，保留笔记。删除笔记会影响所有关联文献。</p>
     <div class="notes-actions"><button :disabled="state.busy || navigationBusy || state.editor.saving || state.documentId!==props.documentId || !state.editor.note.documents.some(document=>document.id===props.documentId)" @click="model.unlink()">解除当前文献关联</button><button :disabled="state.busy || navigationBusy || state.editor.saving || state.documentId!==props.documentId" @click="remove">删除笔记</button></div>
    </section>
   </template>
  </section>
 </ReaderPanel>
</template>
<style scoped>
.notes-content{padding:12px;display:flex;flex-direction:column;gap:12px;overflow:auto;min-width:0;overflow-wrap:anywhere}.notes-content p,.notes-content h3{margin:0}.notes-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.notes-content button{padding:6px 8px;border:1px solid #ddd}.notes-content button:disabled{opacity:.5;cursor:default}.note-list,.note-picker,.note-editor{display:flex;flex-direction:column;gap:8px}.note-list>button,.note-picker>button{justify-content:flex-start;text-align:left;overflow-wrap:anywhere}.note-list>button[aria-pressed=true]{background:#f8eeee;border-color:#9b0000}.note-search{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:8px;border:1px solid #e2e6eb;border-radius:7px;padding:8px;background:#fafbfc}.note-search>label{display:flex;flex-direction:column;gap:5px;min-width:0}.note-search input{box-sizing:border-box;width:100%;min-width:0;border:1px solid #c8ced6;border-radius:5px;padding:8px;font:inherit}.note-search>p,.note-search-results{grid-column:1/-1}.note-search-results{display:flex;flex-direction:column;gap:8px}.note-search-result{display:flex;flex-direction:column;gap:5px;border-left:3px solid #9b0000;background:#fff;padding:8px;min-width:0}.note-search-result>button{text-align:left;font-weight:600;overflow-wrap:anywhere}.note-search-result>button[aria-pressed=true]{background:#f8eeee;border-color:#9b0000}.search-document-count{font-size:11px;color:#687386}.search-match{font-size:12px;line-height:1.5;white-space:pre-wrap}.match-label{display:inline-block;margin-right:5px;border-radius:3px;background:#edf1f5;color:#526176;padding:1px 4px}.search-match mark{background:#ffe28a;color:inherit;padding:0}.note-candidate{display:flex;flex-direction:column;gap:8px;padding:8px;border:1px solid #ddd;border-radius:5px;min-width:0}.note-candidate>button{text-align:left;overflow-wrap:anywhere}.note-picker,.note-editor{border-top:1px solid #ddd;padding-top:12px}.note-editor label{display:flex;flex-direction:column;gap:5px}.note-editor input,.note-editor textarea{width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:5px;padding:8px;font:inherit;min-width:0}.note-editor textarea{min-height:190px;resize:vertical;line-height:1.6}.notes-help{font-size:12px;color:#666}.notes-content [role=alert]{color:#9b0000}
</style>
