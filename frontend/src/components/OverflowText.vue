<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
const props = withDefaults(defineProps<{ text: string; as?: 'span' | 'button' }>(), { as: 'span' })
defineEmits<{ click: [] }>()
const value = ref<HTMLElement>(), overflowing = ref(false)
let observer: ResizeObserver | undefined
function measure() { overflowing.value = !!value.value && value.value.scrollWidth > value.value.clientWidth + 1 }
onMounted(() => { observer = new ResizeObserver(measure); if (value.value) observer.observe(value.value); measure() })
watch(() => props.text, async () => { await nextTick(); measure() })
onUnmounted(() => observer?.disconnect())
</script>
<template>
  <el-tooltip :content="text" :disabled="!overflowing" :show-after="200" effect="light" popper-class="library-popover" placement="top">
    <component :is="as" class="overflow-text" :class="{ 'document-title': as === 'button' }" :type="as === 'button' ? 'button' : undefined" :tabindex="as === 'span' && overflowing ? 0 : undefined" @mouseenter="measure" @focus="measure" @click="$emit('click')">
      <slot /><span ref="value" class="cell-text">{{ text }}</span>
    </component>
  </el-tooltip>
</template>
