<script setup lang="ts">
import { inject, shallowRef } from 'vue'
import { readerPopupRoot } from '../reader/fullscreen'
const popupRoot=inject(readerPopupRoot,shallowRef<HTMLElement>())
import { ArrowDown, Document, Download } from '@element-plus/icons-vue'
import { contentUrl } from '../library'
const props=defineProps<{documentId:string;disabled?:boolean;exportDisabled?:boolean}>()
const emit=defineEmits<{export:[]}>()
function choose(command:string){
  if(command==='export'){emit('export');return}
  const link=document.createElement('a')
  link.href=contentUrl(props.documentId,true);link.click()
}
</script>
<template>
  <el-dropdown :append-to="popupRoot" trigger="click" placement="bottom-end" popper-class="pdf-download-menu" @command="choose">
    <button class="pdf-download-trigger" aria-label="下载 PDF" :disabled="disabled"><Download /><ArrowDown class="download-chevron" /></button>
    <template #dropdown><el-dropdown-menu>
      <el-dropdown-item command="export" aria-label="导出带批注 PDF" :disabled="exportDisabled"><Download /><span><strong>导出带批注 PDF</strong><small>包含当前已保存的批注</small></span></el-dropdown-item>
      <el-dropdown-item command="original" aria-label="下载原始 PDF" divided><Document /><span><strong>下载原始 PDF</strong><small>保留上传时的原始文件</small></span></el-dropdown-item>
    </el-dropdown-menu></template>
  </el-dropdown>
</template>
<style scoped>
.pdf-download-trigger { width:48px; gap:5px }
.pdf-download-trigger .download-chevron { width:12px; height:12px }
</style>
<style>
.pdf-download-menu .el-dropdown-menu { padding:6px }
.pdf-download-menu .el-dropdown-menu__item { gap:12px; padding:12px 16px; line-height:1.4; border-radius:5px }
.pdf-download-menu .el-dropdown-menu__item > svg { width:20px; height:20px; margin:0 }
.pdf-download-menu .el-dropdown-menu__item span { display:flex; flex-direction:column; gap:4px }
.pdf-download-menu strong { font-weight:500; color:var(--litera-text) }
.pdf-download-menu small { font-size:12px; color:var(--litera-muted) }
.pdf-download-menu .is-disabled strong,.pdf-download-menu .is-disabled small { color:inherit }
</style>
