<script setup lang="ts">
// Test utility, not a QA panel. Both Vite flag and server-only fixture must agree.
import {ref,shallowRef,watch} from 'vue'
import {api,ApiError} from '../api'
import {auth} from '../auth'
import {noteCaptureApi,type AnswerSnapshot,type NoteCaptureDraft} from '../notes/captures'
const props=defineProps<{documentId:string}>()
const emit=defineEmits<{'save-to-note':[draft:NoteCaptureDraft]}>()
const available=ref(false),expanded=ref(false),busy=ref(false),error=ref('')
const records=shallowRef<AnswerSnapshot[]>([])
let epoch=0
watch(()=>[props.documentId,auth.user?.id],()=>{epoch++;records.value=[];expanded.value=false;error.value='';available.value=false
 const attempt=epoch
 void noteCaptureApi.config().then(config=>{if(attempt===epoch)available.value=!!config.aiAnswerCapture?.isolatedMock && config.aiAnswerCapture.available}).catch(()=>{})
},{immediate:true})
async function load(){
 expanded.value=!expanded.value
 if(!expanded.value)return
 const attempt=epoch;busy.value=true;error.value=''
 try{const values=await api<AnswerSnapshot[]>('/notes/mock-answers/list?documentId='+encodeURIComponent(props.documentId));if(attempt===epoch)records.value=values}
 catch(e){if(attempt===epoch)error.value=e instanceof ApiError?e.message:'无法读取模拟回答。'}
 finally{if(attempt===epoch)busy.value=false}
}
function save(record:AnswerSnapshot){emit('save-to-note',{source:{kind:'ai_answer',answerId:record.answerId,answerRevision:record.answerRevision,historical:false,confirmHistorical:false,confirmUncited:false},title:record.contextDocument.title})}
</script>
<template>
 <section v-if="available" class="mock-answer-preview" aria-label="隔离模拟问答验收工具">
  <button type="button" @click="load">{{expanded?'收起模拟问答验收工具':'模拟问答保存验收（非真实AI）'}}</button>
  <div v-if="expanded">
   <p>仅用于笔记适配验收：不提问、不调用模型、不存储问答记录。仅识别下面的合成PDF。</p>
   <a href="/api/v1/notes/mock-answers/fixture.pdf" download>下载合成测试PDF</a>
   <p v-if="busy" role="status">正在读取固定模拟记录…</p><p v-if="error" role="alert">{{error}}</p>
   <p v-if="!busy && !error && !records.length">请将合成测试PDF上传到此隔离环境，再打开该文献使用此工具；现有论文不生成模拟引用。</p>
   <article v-for="record in records" :key="record.answerId">
    <strong>{{record.evidenceState==='verified'?'合成PDF核验引用（Mock）':'无引用回答（Mock，未核实）'}}</strong>
    <p>{{record.question}}</p><p>{{record.answer}}</p>
    <button type="button" :aria-label="record.evidenceState==='verified'?'保存模拟引用回答到笔记':'保存模拟无引用回答到笔记'" @click="save(record)">保存到笔记</button>
   </article>
  </div>
 </section>
</template>
<style scoped>
.mock-answer-preview{font-size:12px;margin:4px 16px;padding:6px;border:1px dashed #b89546;background:#fff9e8;max-height:200px;overflow:auto}.mock-answer-preview p{margin:6px 0}.mock-answer-preview article{border-top:1px solid #dfcfab;margin-top:8px;padding-top:8px}button{font:inherit;cursor:pointer}
</style>
