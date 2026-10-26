<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { ApiError } from '../api'
import type { NoteDTO, NotesPage } from '../notes'
import { captureDocumentId, captureDraftIssue, noteCaptureApi, type CaptureConfig, type CaptureRequest, type NoteCaptureDraft } from '../notes/captures'
import { nativeFullscreenEscape } from '../reader/fullscreen'
const props=defineProps<{draft:NoteCaptureDraft|null;preferredNote:NoteDTO|null;ownerId:string}>()
const emit=defineEmits<{captured:[note:NoteDTO];close:[]}>()
const dialog=ref<HTMLDialogElement>(), frozen=shallowRef<NoteCaptureDraft|null>(null), config=shallowRef<CaptureConfig|null>(null)
const checking=ref(false), reading=ref(false), saving=ref(false), error=ref(''), info=ref('')
const target=ref<'new'|'current'|'other'>('new'), title=ref(''), query=ref(''), appliedQuery=ref('')
const notes=ref<NotesPage>({items:[],page:1,pageSize:20,total:0}), selected=shallowRef<NoteDTO|null>(null)
const association=ref<''|'link'|'keep'>(''), historyConfirmed=ref(false), uncertain=ref(false), conflict=ref(false)
const pending=shallowRef<CaptureRequest|null>(null)
let epoch=0, readToken=0, searchToken=0
const issue=computed(()=>frozen.value?captureDraftIssue(frozen.value,config.value):'')
const deployed=computed(()=>!!config.value?.available && config.value.formatVersion===1)
const locked=computed(()=>saving.value || uncertain.value || conflict.value)
const documentId=computed(()=>captureDocumentId(frozen.value))
const pdfSource=computed(()=>frozen.value?.source.kind!=='ai_answer'?frozen.value?.source:null)
const answerPreview=computed(()=>frozen.value?.source.kind==='ai_answer'?frozen.value.answerPreview:null)
const uncitedConfirmed=ref(false)
const uncitedRequired=computed(()=>answerPreview.value?.evidenceState==='none')
const linked=computed(()=>!!selected.value?.documents.some(item=>item.id===documentId.value))
const historyRequired=computed(()=>!!frozen.value?.source.historical)
const canSave=computed(()=>!!frozen.value && !!props.ownerId && deployed.value && !checking.value && !reading.value && !saving.value && !conflict.value && !issue.value && (!historyRequired.value || historyConfirmed.value) && (!uncitedRequired.value || uncitedConfirmed.value) && (uncertain.value || (target.value==='new' ? !!title.value.trim() && title.value.trim().length<=200 : !!selected.value && (linked.value || !!association.value))))
const sourceLabel=computed(()=>frozen.value?.source.kind==='ai_answer' && !answerPreview.value?'AI 回答 · 来源尚未核验':answerPreview.value?`${answerPreview.value.contextDocument.title || '未命名文献'} · AI回答（非PDF原文）`:`${frozen.value?.title.trim() || '未命名文献'} · PDF 第 ${pdfSource.value?.pageNumber ?? '?'} 页`)
const safeMessage=(value:unknown)=>value instanceof ApiError?value.message:'保存失败，请稍后重试；原文和译文已保留。'
function current(scope:number){return scope===epoch && !!props.draft && !!props.ownerId}
function requestClose(){if(!saving.value)emit('close')}
async function show(){await nextTick();if(!frozen.value || !dialog.value)return;try{if(!dialog.value.open)dialog.value.showModal()}catch{dialog.value.open=true}}
async function loadTarget(id:string){
  const scope=epoch,token=++readToken;reading.value=true;selected.value=null;association.value='';error.value=''
  try{const value=await noteCaptureApi.get(id);if(current(scope) && token===readToken){selected.value=value;association.value=value.documents.some(item=>item.id===documentId.value)?'keep':''}}
  catch(value){if(current(scope) && token===readToken)error.value=safeMessage(value)}
  finally{if(current(scope) && token===readToken)reading.value=false}
}
async function chooseTarget(value:'new'|'current'|'other'){
  if(locked.value)return
  target.value=value;readToken++;searchToken++;selected.value=null;reading.value=false;association.value='';pending.value=null;error.value='';info.value=''
  if(value==='current' && props.preferredNote)await loadTarget(props.preferredNote.id)
  else if(value==='other')await search(1)
}
async function search(page=1){
  if(locked.value)return
  const scope=epoch,token=++searchToken;reading.value=true;error.value=''
  if(page===1)appliedQuery.value=query.value
  try{const value=await noteCaptureApi.list(appliedQuery.value,page);if(current(scope) && token===searchToken)notes.value=value}
  catch(value){if(current(scope) && token===searchToken)error.value=safeMessage(value)}
  finally{if(current(scope) && token===searchToken)reading.value=false}
}
async function selectNote(id:string){if(!locked.value)await loadTarget(id)}
async function submit(){
  if(!canSave.value || !frozen.value)return
  if(!uncertain.value){
    pending.value={operationId:crypto.randomUUID(),noteId:target.value==='new'?crypto.randomUUID():selected.value!.id,version:target.value==='new'?null:selected.value!.version,newNoteTitle:target.value==='new'?title.value.trim():null,associationMode:target.value==='new'?'link':linked.value?'keep':association.value as 'link'|'keep',source:JSON.parse(JSON.stringify({...frozen.value.source,confirmHistorical:historyRequired.value?historyConfirmed.value:false,...(frozen.value.source.kind==='ai_answer'?{confirmUncited:uncitedRequired.value?uncitedConfirmed.value:false}:{})}))}
  }
  const request=pending.value!,scope=epoch;saving.value=true;error.value='';info.value=''
  try{
    const result=await noteCaptureApi.save(request)
    if(!current(scope))return
    uncertain.value=false;pending.value=null;emit('captured',result.note)
  }catch(value){
    if(!current(scope))return
    error.value=safeMessage(value)
    // A lost response may follow a committed transaction. Reuse the exact same
    // operation and payload; do not create another note or append twice.
    uncertain.value=!(value instanceof ApiError) || value.status===0 || value.status>=500
    conflict.value=value instanceof ApiError && value.status===409
    if(uncertain.value)info.value='保存结果尚未确认。重试将核实同一操作，不会重复插入；目标与来源暂时锁定。'
    else if(conflict.value)info.value='目标笔记或关联已变化。请重新读取目标笔记，检查后再次点击保存；本次没有覆盖内容。'
    else pending.value=null
  }finally{if(current(scope))saving.value=false}
}
async function reloadTarget(){
  if(!conflict.value || !pending.value || saving.value)return
  const id=pending.value.noteId
  conflict.value=false;pending.value=null
  if(target.value==='new'){target.value='other'}
  await loadTarget(id)
  if(selected.value)info.value='已重新读取目标笔记。请核对目标和关联方式，然后再次点击保存摘录。'
}
watch(()=>[props.draft,props.ownerId] as const,async()=>{
  const scope=++epoch;readToken++;searchToken++;frozen.value=props.draft?JSON.parse(JSON.stringify(props.draft)):null
  if(frozen.value?.source.kind==='ai_answer')delete frozen.value.answerPreview
  config.value=null;error.value='';info.value='';checking.value=false;reading.value=false;saving.value=false;uncertain.value=false;conflict.value=false;pending.value=null;selected.value=null;association.value='';historyConfirmed.value=false;uncitedConfirmed.value=false;query.value='';appliedQuery.value='';notes.value={items:[],page:1,pageSize:20,total:0}
  if(!frozen.value || !props.ownerId){dialog.value?.close();return}
  title.value=frozen.value.source.kind==='ai_answer'?'AI 回答笔记':frozen.value.source.kind==='translation_excerpt'?'翻译摘录':'PDF 原文摘录'
  target.value=props.preferredNote?'current':'new'
  void show();checking.value=true
  try{const value=await noteCaptureApi.config();if(!current(scope))return;config.value=value;if(!value.available || value.formatVersion!==1)error.value='摘录功能尚未部署，请等待预览环境升级。'
    if(frozen.value?.source.kind==='ai_answer' && value.aiAnswerCapture?.available){
      // Fetch an authoritative preview in the current auth/dialog scope. The
      // subsequent POST still contains only the answer reference and confirms.
      const source=frozen.value.source,preview=await noteCaptureApi.answerPreview(source.answerId,source.answerRevision)
      if(!current(scope) || !frozen.value)return
      frozen.value={...frozen.value,answerPreview:preview}
    }}
  catch(value){if(current(scope))error.value=value instanceof ApiError && value.status===404?'摘录功能尚未部署，请等待预览环境升级。':safeMessage(value);return}
  finally{if(current(scope))checking.value=false}
  if(current(scope) && deployed.value && target.value==='current' && props.preferredNote)await loadTarget(props.preferredNote.id)
},{immediate:true})
onBeforeUnmount(()=>{epoch++;readToken++;searchToken++;dialog.value?.close()})
</script>
<template>
  <dialog v-if="frozen" ref="dialog" class="note-capture-dialog" aria-label="保存到文献笔记" @cancel.prevent="!nativeFullscreenEscape() && requestClose()">
    <form @submit.prevent="submit">
      <header><h2>保存到文献笔记</h2><button type="button" aria-label="取消保存到笔记" :disabled="saving" @click="requestClose">×</button></header>
      <section class="capture-preview" aria-label="待保存的来源摘录">
        <strong>{{ sourceLabel }}</strong>
        <span v-if="frozen.source.historical" class="badge">历史结果及其原来源</span>
        <template v-if="answerPreview">
          <span v-if="answerPreview.provenance==='isolated_mock'" class="badge mock">模拟问答数据 · 非真实AI问答联调</span>
          <p>问题</p><blockquote>{{answerPreview.question}}</blockquote>
          <p>AI 回答（非 PDF 原文）</p><div class="capture-text" data-testid="note-capture-answer">{{answerPreview.answer}}</div>
          <p>{{answerPreview.evidenceState==='none'?'未核实：没有可信引用，不声称来源页码。':'引用单独核验，回答本身仍为AI生成内容。'}}</p>
          <blockquote v-for="citation in answerPreview.citations" :key="citation.citationId">{{citation.title}} · PDF 第 {{citation.pageNumber}} 页<br>{{citation.quote}}</blockquote>
        </template>
        <template v-else-if="pdfSource">
          <span v-if="pdfSource.translationProof?.provenance==='isolated_mock'" class="badge mock">隔离 Mock 译文（非真实模型）</span>
          <p>原文</p><blockquote data-testid="note-capture-original">{{ pdfSource.originalText }}</blockquote>
          <template v-if="pdfSource.kind==='translation_excerpt'"><p>译文</p><div class="capture-text" data-testid="note-capture-translation">{{ pdfSource.translatedText }}</div></template>
        </template>
      </section>
      <p v-if="checking" role="status">正在检查摘录功能…</p>
      <fieldset :disabled="locked || checking || !deployed"><legend>保存位置</legend>
        <label><input type="radio" name="capture-target" :checked="target==='new'" @change="chooseTarget('new')">新建笔记</label>
        <label v-if="preferredNote"><input type="radio" name="capture-target" :checked="target==='current'" @change="chooseTarget('current')" aria-label="当前笔记">当前笔记 <span>（{{ preferredNote.title || '未命名笔记' }}）</span></label>
        <label><input type="radio" name="capture-target" :checked="target==='other'" @change="chooseTarget('other')">其他已有笔记</label>
        <template v-if="target==='new'">
          <label class="field-label">新笔记标题<input v-model="title" aria-label="新笔记标题" maxlength="200"></label>
          <p class="hint">新笔记将关联来源文献。个人正文保持为空，摘录作为独立来源内容块保存。</p>
        </template>
        <div v-if="target==='other'" class="note-choice">
          <div class="search-row"><label>搜索已有笔记标题<input v-model="query" aria-label="搜索已有笔记标题" maxlength="200" @keydown.enter.prevent="search(1)"></label><button type="button" :disabled="reading" @click="search(1)">搜索笔记</button></div>
          <ul><li v-for="note in notes.items" :key="note.id"><button type="button" :aria-label="'选择笔记：'+(note.title || '未命名笔记')" :aria-pressed="selected?.id===note.id" :disabled="reading" @click="selectNote(note.id)">{{ note.title || '未命名笔记' }}</button></li></ul>
          <p v-if="!reading && !notes.items.length">没有符合标题的个人笔记。</p>
          <div class="pagination"><button type="button" :disabled="reading || notes.page<=1" @click="search(notes.page-1)">上一页笔记</button><span>第 {{ notes.page }} 页</span><button type="button" :disabled="reading || notes.page*notes.pageSize>=notes.total" @click="search(notes.page+1)">下一页笔记</button></div>
        </div>
      </fieldset>
      <p v-if="reading" role="status">正在读取目标笔记…</p>
      <section v-if="target!=='new' && selected" class="capture-target-summary">
        <strong>目标笔记：{{ selected.title || '未命名笔记' }}</strong><p class="hint">只追加独立摘录，不改写笔记标题或个人正文。</p>
        <p v-if="linked">已关联来源文献，现有关联保持不变。</p>
        <fieldset v-else :disabled="locked"><legend>目标笔记尚未关联来源文献，请选择</legend>
          <label><input v-model="association" type="radio" name="capture-association" value="link">同时关联来源文献</label>
          <label><input v-model="association" type="radio" name="capture-association" value="keep">仅保存来源，不新增关联</label>
        </fieldset>
      </section>
      <label v-if="historyRequired" class="history-confirm"><input v-model="historyConfirmed" type="checkbox" :disabled="locked">{{frozen.source.kind==='ai_answer'?'确认保存此历史AI回答及其原来源':'确认保存上一条译文及其原来源'}}</label>
      <label v-if="uncitedRequired" class="history-confirm"><input v-model="uncitedConfirmed" type="checkbox" :disabled="locked">我确认将无可信引用的AI回答保存为未核实内容</label>
      <p v-if="error" role="alert">{{ error }}</p><p v-else-if="issue" role="alert">{{ issue }}</p><p v-if="info" role="status">{{ info }}</p>
      <footer><button type="button" :disabled="saving" @click="requestClose">取消</button><button v-if="conflict" type="button" :disabled="reading" @click="reloadTarget">重新读取目标笔记</button><button v-else-if="uncertain" type="submit" :disabled="!canSave">重试保存</button><button v-else type="submit" aria-label="保存摘录" :disabled="!canSave">{{ saving?'保存中…':'保存摘录' }}</button></footer>
    </form>
  </dialog>
</template>
<style scoped>
.note-capture-dialog{width:min(640px,calc(100vw - 32px));max-height:calc(100dvh - 40px);padding:20px;border:1px solid #d9e0e7;border-radius:12px;color:#253246;overflow:auto;box-sizing:border-box}.note-capture-dialog::backdrop{background:#17223866}header,footer,.search-row,.pagination{display:flex;align-items:center;gap:10px}header{justify-content:space-between}h2{font-size:18px;margin:0}footer{justify-content:flex-end;margin-top:18px;flex-wrap:wrap}button,input{font:inherit}button{padding:6px 10px;cursor:pointer}button:disabled{cursor:default;opacity:.55}fieldset{border:1px solid #dce3e9;border-radius:7px;margin:14px 0;padding:12px}fieldset>label{display:block;margin:8px 0}.field-label input{display:block;width:100%;box-sizing:border-box;margin-top:6px}.hint{font-size:13px;color:#637084}.capture-preview{background:#f5f8fc;padding:12px;margin-top:16px;border-radius:7px;overflow-wrap:anywhere}.capture-preview strong{display:block}.capture-preview p{font-size:13px;color:#637084;margin-bottom:4px}.capture-preview blockquote,.capture-text{white-space:pre-wrap;max-height:170px;overflow:auto;margin:0}.capture-preview blockquote{border-left:3px solid #93a7c5;padding-left:10px}.badge{display:inline-block;font-size:12px;padding:3px 6px;margin-top:8px;background:#e5edf6;border-radius:4px}.mock{background:#fff0c9;color:#684d0a}.note-choice ul{list-style:none;margin:10px 0;padding:0;max-height:170px;overflow:auto}.note-choice li button{text-align:left;overflow-wrap:anywhere;width:100%;margin:3px 0}.note-choice [aria-pressed=true]{outline:2px solid #3665b0}.search-row label{min-width:0;flex:1}.search-row input{display:block;width:100%;box-sizing:border-box}.pagination{font-size:13px}.history-confirm{display:block;margin:12px 0}[role=alert]{color:#a32d2d;overflow-wrap:anywhere}[role=status]{font-size:13px;color:#50627a}.capture-target-summary{overflow-wrap:anywhere}@media(max-width:500px){.note-capture-dialog{padding:12px}.search-row{align-items:end;flex-wrap:wrap}.pagination{gap:5px;flex-wrap:wrap}}
</style>
