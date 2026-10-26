<script setup lang="ts">
import type {NoteDocument} from '../notes'
const props=withDefaults(defineProps<{
 documents:NoteDocument[]
 currentDocumentId:string
 disabled?:boolean
 label?:string
}>(),{disabled:false,label:'关联文献'})
const emit=defineEmits<{'open-document':[documentId:string]}>()
function title(document:NoteDocument){return document.title.trim() ? document.title : '未命名文献'}
function openDocument(id:string){if(!props.disabled && id!==props.currentDocumentId)emit('open-document',id)}
</script>
<template>
 <section class="note-documents" :aria-label="label">
  <h3>关联文献（{{documents.length}}）</h3>
  <p v-if="!documents.length" class="note-documents-empty">尚未关联文献</p>
  <ul v-else>
   <li v-for="document in documents" :key="document.id" :data-document-id="document.id" :data-current="document.id===currentDocumentId">
    <span v-if="document.id===currentDocumentId" class="note-document-title" :title="title(document)">{{title(document)}}</span>
    <button v-else type="button" class="note-document-title note-document-link" :title="title(document)" :aria-label="`打开关联文献：${title(document)}`" :disabled="disabled" @click="openDocument(document.id)">{{title(document)}}</button>
    <span v-if="document.id===currentDocumentId" class="note-document-current">当前文献</span>
   </li>
  </ul>
 </section>
</template>
<style scoped>
.note-documents{min-width:0;display:flex;flex-direction:column;gap:7px}.note-documents h3{font-size:13px;font-weight:600;margin:0}.note-documents ul{display:flex;flex-direction:column;gap:7px;padding:0;margin:0;list-style:none}.note-documents li{display:flex;align-items:flex-start;gap:8px;min-width:0;line-height:1.5}.note-document-title{flex:1;min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;text-align:left;font:inherit}.note-document-link{border:0;background:none;padding:0;color:#9b0000;cursor:pointer}.note-document-link:hover{text-decoration:underline}.note-document-link:focus-visible{outline:2px solid #9b0000;outline-offset:2px}.note-document-link:disabled{opacity:.5;cursor:default;text-decoration:none}.note-document-current{flex:none;font-size:11px;border-radius:4px;background:#f8eeee;color:#8e0000;padding:1px 5px;white-space:nowrap}.note-documents-empty{font-size:12px;color:#666;margin:0}
</style>
