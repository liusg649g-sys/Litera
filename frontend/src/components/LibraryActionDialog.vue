<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElDialog, ElButton } from 'element-plus'
defineProps<{ title: string; busy: boolean; error: string; confirm: string; confirmDisabled?: boolean; dialogClass?: string }>()
const emit = defineEmits<{ close: []; confirm: [] }>()
const body = ref<HTMLElement>()
function focus() { void nextTick(() => body.value?.querySelector<HTMLElement>('input,button')?.focus()) }
function key(event: KeyboardEvent) { if (event.key === 'Escape') event.stopPropagation() }
onMounted(() => window.addEventListener('keydown', key))
onUnmounted(() => window.removeEventListener('keydown', key))
</script>
<template>
  <el-dialog :model-value="true" :title="title" width="420px" class="library-action-dialog" :class="dialogClass" align-center :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy" @close="emit('close')" @opened="focus">
    <div ref="body"><slot /><p v-if="error" role="alert" class="action-error">{{ error }}</p></div>
    <template #footer><el-button :disabled="busy" @click="emit('close')">取消</el-button><el-button type="primary" :loading="busy" :disabled="confirmDisabled" @click="emit('confirm')">{{ confirm }}</el-button></template>
  </el-dialog>
</template>
