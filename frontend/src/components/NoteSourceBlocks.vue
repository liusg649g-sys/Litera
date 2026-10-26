<script setup lang="ts">
import { computed } from 'vue'
import AiAnswerNoteBlock from './AiAnswerNoteBlock.vue'
import type { NoteDocument } from '../notes'
import { storedSourceBlock, storedAiAnswer, type StoredSourceBlock, type StoredAiAnswerBlock, type NoteSourceLocation } from '../notes/captures'
const props=defineProps<{sources:unknown[];documents:NoteDocument[];disabled?:boolean;navigatingId?:string}>()
const emit=defineEmits<{'navigate-source':[block:NoteSourceLocation]}>()
const blocks=computed(()=>props.sources.map(value=>storedSourceBlock(value)||storedAiAnswer(value)).filter((value):value is StoredSourceBlock|StoredAiAnswerBlock=>!!value))
const unknownCount=computed(()=>props.sources.length-blocks.value.length)
const associated=(id:string)=>props.documents.some(document=>document.id===id)
function pages(block:StoredSourceBlock){const pages=Array.isArray(block.source.pageNumbers)?block.source.pageNumbers.filter(page=>Number.isInteger(page)&&page>0):[];return pages.length?pages.join('、'):String(block.source.pageNumber)}
function direction(block:StoredSourceBlock){return block.sourceLanguage==='en' && block.targetLanguage==='zh'?'英译中':block.sourceLanguage==='zh' && block.targetLanguage==='en'?'中译英':'翻译方向未标注'}
function locationIssue(block:StoredSourceBlock){
  if(!block.source.documentId.trim())return '缺少有效的来源文献标识。'
  if(!Number.isInteger(block.source.pageNumber) || block.source.pageNumber<1)return '来源物理页码无效。'
  if(!/^[a-f0-9]{64}$/i.test(block.source.fileSha256 || ''))return '缺少有效的 PDF 版本信息。'
  return ''
}
</script>
<template>
  <section v-if="sources.length" class="note-source-blocks" aria-label="笔记来源摘录">
    <h3>来源摘录（{{ sources.length }}）</h3><p class="sources-help">摘录按保存顺序展示，与上方个人正文独立保存。来源保持保存时的文献与 PDF 页码。</p>
    <template v-for="block in blocks" :key="block.id">
    <AiAnswerNoteBlock v-if="block.kind==='ai_answer'" :block="block" :disabled="disabled" @navigate-source="emit('navigate-source',$event)" />
    <article v-else class="note-source-block" data-testid="note-source-block" :data-source-block-id="block.id" :data-source-document-id="block.source.documentId" :data-source-page="block.source.pageNumber">
      <h4>{{ block.kind==='pdf_excerpt'?'PDF 原文摘录':'原文与译文摘录' }}</h4>
      <div class="block-source-row"><p class="block-source" :title="block.source.title">{{ block.source.title.trim() || '未命名文献' }} · PDF 第 {{ pages(block) }} 页</p><button type="button" :aria-label="`查看原文：${block.source.title.trim() || '未命名文献'}，PDF 第 ${block.source.pageNumber} 页`" :disabled="disabled || !!locationIssue(block)" @click="emit('navigate-source',block)">{{navigatingId===block.id?'正在定位…':'查看原文'}}</button></div>
      <p v-if="locationIssue(block)" class="source-status" role="alert">无法可靠定位来源：{{locationIssue(block)}}</p>
      <p v-if="!associated(block.source.documentId)" class="source-status">来源文献当前未关联</p>
      <div v-if="block.kind==='translation_excerpt'" class="block-labels"><span>{{ direction(block) }}</span><span v-if="block.historical">历史译文快照</span><span v-if="block.translationProvenance==='isolated_mock'" class="mock">隔离 Mock 译文（非真实模型）</span><span v-else-if="block.translationProvenance==='model_api'">模型译文</span><span v-else>译文来源尚未验证</span></div>
      <p class="text-label">PDF 原文</p><blockquote data-testid="note-block-original">{{ block.originalText }}</blockquote>
      <template v-if="block.kind==='translation_excerpt'"><p class="text-label">译文</p><p class="block-translation" data-testid="note-block-translation">{{ block.translatedText }}</p></template>
      <details v-if="block.modelInputText && block.modelInputText!==block.originalText"><summary>模型输入的断词处理（原文已保留）</summary><p v-if="block.normalizationCount">合并 {{ block.normalizationCount }} 处有 PDF 换行证据的断词。</p><p class="block-translation">{{ block.modelInputText }}</p></details>
    </article>
    </template>
    <p v-if="unknownCount" class="source-status">存在 {{ unknownCount }} 条当前版本无法识别的来源记录，原数据已保留。</p>
  </section>
</template>
<style scoped>
.note-source-blocks{border-top:1px solid #dce3ea;margin-top:18px;padding-top:12px;overflow-wrap:anywhere}h3{font-size:15px;margin:0 0 6px}h4{font-size:14px;margin:0 0 6px}.sources-help{font-size:12px;color:#657387}.note-source-block{background:#f5f8fc;border:1px solid #dce5ee;border-radius:8px;padding:12px;margin:12px 0}.block-source-row{display:flex;align-items:flex-start;gap:8px}.block-source{flex:1;min-width:0;font-size:13px;font-weight:600;white-space:normal;margin:4px 0 8px}.block-source-row button{flex:none}.source-status{font-size:12px;color:#80612d}.block-labels{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}.block-labels span{font-size:11px;background:#e6edf7;border-radius:3px;padding:3px 5px}.block-labels .mock{background:#fff0c9;color:#684d0a}.text-label{color:#64748b;font-size:12px;margin:12px 0 4px}blockquote{white-space:pre-wrap;margin:0;border-left:3px solid #9badc6;padding-left:10px;color:#26384e}.block-translation{white-space:pre-wrap;margin:0}details{font-size:12px;margin-top:12px}summary{cursor:pointer;color:#506583}
</style>