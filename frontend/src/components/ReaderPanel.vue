<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { startPointerResize } from '../resize'
import { clampSidebar } from '../library'
const props = defineProps<{ open: boolean; side: 'left'|'right'; label: string; width?: number; resizable?: boolean; fixedContent?: boolean; nonModal?: boolean }>()
const emit = defineEmits<{ close: []; 'update:width': [number] }>()
const narrow = ref(window.innerWidth < 1100), dialog = ref<HTMLDialogElement>()
let returnFocus: HTMLElement | null = null
let stopDrag: (() => void) | undefined
function resize(event: PointerEvent) { stopDrag?.(); stopDrag = startPointerResize(event, props.width || 240, width => emit('update:width', clampSidebar(width))) }
function resizeKey(event: KeyboardEvent) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault(); emit('update:width', clampSidebar((props.width || 240) + (event.key === 'ArrowRight' ? 10 : -10)))
}
async function sync() {
  await nextTick()
  if (dialog.value?.open && props.nonModal === dialog.value.matches(':modal')) dialog.value.close()
  if (props.open && narrow.value && dialog.value && !dialog.value.open) {
    returnFocus = document.activeElement as HTMLElement
    if (props.nonModal) dialog.value.show(); else dialog.value.showModal()
  } else if ((!props.open || !narrow.value) && dialog.value?.open) { dialog.value.close(); returnFocus?.focus() }
}
function resized() { narrow.value = window.innerWidth < 1100; void sync() }
watch(() => [props.open, narrow.value, props.nonModal], sync)
onMounted(() => { window.addEventListener('resize', resized); void sync() })
onBeforeUnmount(() => { stopDrag?.(); window.removeEventListener('resize', resized); dialog.value?.close() })
</script>
<template>
  <dialog v-if="narrow" ref="dialog" class="reader-panel reader-panel-dialog" :style="width ? { width: width + 'px' } : undefined" :class="[side, { 'reader-panel-fixed': fixedContent }]" :aria-label="label" @cancel.prevent="emit('close')" @click="($event.target === dialog) && emit('close')">
    <header><strong>{{ label }}</strong><button :aria-label="`关闭${label}`" @click="emit('close')">×</button></header><slot />
  </dialog>
  <aside v-else v-show="open" class="reader-panel" :style="width ? { width: width + 'px' } : undefined" :class="[side, { 'reader-panel-fixed': fixedContent }]" :aria-label="label">
    <header><strong>{{ label }}</strong><button :aria-label="`关闭${label}`" @click="emit('close')">×</button></header><slot />
  </aside>
  <div v-if="open && !narrow && resizable" class="reader-panel-resizer" role="separator" aria-label="调整文献导航宽度" aria-orientation="vertical" tabindex="0" :aria-valuenow="width || 240" :aria-valuemin="180" :aria-valuemax="320" @pointerdown="resize" @keydown="resizeKey" />
</template>
