<script setup lang="ts">
import { CircleCheckFilled, InfoFilled, Loading, WarningFilled } from '@element-plus/icons-vue'
defineProps<{phase:string;error:string;conflict?:boolean}>()
const emit=defineEmits<{resolve:[];start:[];cancel:[];retry:[];reload:[]}>()
</script>
<template>
  <div v-if="phase!=='idle'" class="reader-notice pdf-export-status" :role="phase==='failed'?'alert':'status'">
    <component :is="phase==='done'?CircleCheckFilled:phase==='running'?Loading:phase==='failed'?WarningFilled:InfoFilled" class="pdf-export-status-icon" :class="{ 'is-loading':phase==='running', 'is-success':phase==='done' }" aria-hidden="true" />
    <template v-if="phase==='choice'">有未保存的批注或插入草稿。导出只包含已保存快照，草稿将保留。<button @click="emit('resolve')">返回处理草稿</button><button @click="emit('start')">仅导出已保存内容</button><button @click="emit('cancel')">取消导出</button></template>
    <template v-else-if="phase==='running'">正在导出带批注 PDF… 可继续阅读和编辑。<button @click="emit('cancel')">取消导出</button></template>
    <template v-else-if="phase==='done'">带批注 PDF 已生成并开始下载。<button @click="emit('cancel')">关闭</button></template>
    <template v-else>{{ error }}<template v-if="conflict"><span>载入最新批注会清空本次撤销历史。</span><button @click="emit('reload')">载入最新批注</button></template><button @click="emit('retry')">重试导出</button><button @click="emit('cancel')">关闭</button></template>
  </div>
</template>
