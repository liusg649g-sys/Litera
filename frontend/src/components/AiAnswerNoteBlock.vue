<script setup lang="ts">
import type {StoredAiAnswerBlock,NoteSourceLocation} from '../notes/captures'
const props=defineProps<{block:StoredAiAnswerBlock;disabled?:boolean}>()
const emit=defineEmits<{'navigate-source':[location:NoteSourceLocation]}>()
function navigate(index:number){
 const c=props.block.citations[index]
 if(!c)return
 emit('navigate-source',{id:props.block.id+':'+c.citationId,source:{documentId:c.documentId,title:c.title,fileSha256:c.fileSha256,pageNumber:c.pageNumber,positions:[]}})
}
</script>
<template>
 <article class="ai-note-block" data-testid="ai-answer-note-block" :data-source-block-id="block.id">
  <h4>AI 回答</h4>
  <p v-if="block.answerRef.provenance==='isolated_mock'" class="mock">模拟问答数据 · 非真实AI问答联调</p>
  <p>{{block.contextDocument.title || '未命名文献'}} · 回答修订 {{block.answerRef.answerRevision}}</p>
  <p v-if="block.historical">历史回答快照，来源保持保存时状态。</p>
  <strong>问题</strong><p class="text">{{block.question}}</p>
  <strong>AI 生成的回答（非 PDF 原文）</strong><p class="text" data-testid="saved-ai-answer">{{block.answer}}</p>
  <p v-if="block.evidenceState==='none'" class="warning">未核实 · 无可信引用；不声称任何来源页码。</p>
  <p v-else>以下引用经服务端核验；不代表AI回答的所有推断均已证实。</p>
  <section v-for="(citation,index) in block.citations" :key="citation.citationId" class="citation">
   <p>{{citation.title || '未命名文献'}} · PDF 第 {{citation.pageNumber}} 页</p>
   <blockquote>{{citation.quote}}</blockquote>
   <button type="button" :disabled="disabled" @click="navigate(index)">查看引用原文</button>
   <small>仅页码定位；无 PDF.js 选区，不显示精确高亮。</small>
  </section>
 </article>
</template>
<style scoped>
.ai-note-block{margin:12px 0;padding:12px;border:1px solid #dce5ee;border-radius:8px;background:#f5f8fc;font-size:13px;overflow-wrap:anywhere}.ai-note-block h4{margin:0 0 8px}.text,blockquote{white-space:pre-wrap}.mock,.warning{color:#80612d;background:#fff0c9;padding:6px;border-radius:4px}.citation{border-top:1px solid #dae2ea;margin-top:12px;padding-top:8px}.citation blockquote{margin:8px 0;border-left:3px solid #9badc6;padding-left:10px}.citation small{display:block;margin-top:6px;color:#64748b}
</style>
