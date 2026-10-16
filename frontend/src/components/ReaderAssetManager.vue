<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { assetPath,discardAsset,type ReaderAsset } from '../reader/assets'
const props=defineProps<{documentId:string}>(),emit=defineEmits<{close:[]}>()
const items=ref<ReaderAsset[]>([]),error=ref(''),busy=ref(false)
async function load(){busy.value=true;error.value='';try{items.value=(await api<{items:ReaderAsset[]}>(assetPath(props.documentId))).items}catch(e:any){error.value=e.message}finally{busy.value=false}}
async function remove(a:ReaderAsset){busy.value=true;error.value='';try{const result=await discardAsset(props.documentId,a.assetId);if(result)error.value='清理失败已登记，可再次重试。';items.value=(await api<{items:ReaderAsset[]}>(assetPath(props.documentId))).items}catch(e:any){error.value=e.message}finally{busy.value=false}}
onMounted(load)
</script>
<template><section class="signature-pad asset-manager" aria-label="图片资产管理" @keydown.stop @keydown.esc.prevent.stop="emit('close')"><header><strong>本篇图片资产</strong><button aria-label="关闭资产管理" @click="emit('close')">×</button></header><p>未引用上传1小时后回收；删除对象后保留24小时供撤销。</p><p v-if="error" role="status">{{ error }}</p><div class="asset-entries"><article v-for="a in items" :key="a.assetId"><span>{{ a.mimeType==='image/png'?'PNG':'JPEG' }} · {{ a.width }} × {{ a.height }} · {{ Math.ceil(a.sizeBytes/1024) }} KiB</span><small>{{ a.status==='failed'?'清理失败':a.status==='ready'?'可用':a.status==='cleaning'?'待重试清理':'上传未完成' }} {{ a.errorCode }} · 清理尝试 {{ a.attempts }}</small><button :disabled="busy" @click="remove(a)">{{ a.status==='failed' || a.status==='cleaning'?'重试清理':'清理未引用图片' }}</button></article><p v-if="!items.length">暂无图片资产</p></div><button :disabled="busy" @click="load">刷新状态</button></section></template>
