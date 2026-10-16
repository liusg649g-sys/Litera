<script setup lang="ts">
import { annotationColors, type AnnotationDTO } from '../reader/annotations'
const props = defineProps<{ item: AnnotationDTO; disabled?: boolean }>()
const emit = defineEmits<{ change: [AnnotationDTO] }>()
function color(value: string) { emit('change', { ...props.item, color: value }) }
function style(key: 'opacity' | 'fontSize' | 'lineWidth', event: Event) {
  emit('change', { ...props.item, style: { ...props.item.style, [key]: Number((event.target as HTMLInputElement).value) } })
}
</script>
<template>
  <fieldset class="annotation-properties" :disabled="disabled">
    <div v-if="!['image','signature'].includes(item.type)" class="annotation-editor-colors" role="group" aria-label="批注颜色选择"><span>颜色</span><button v-for="c in annotationColors" :key="c" type="button" class="reader-color" :style="{ '--swatch': c }" :aria-label="`编辑批注颜色 ${c}`" :aria-pressed="item.color.toUpperCase()===c" @click="color(c)" /><label>自定义<input :value="item.color" aria-label="编辑批注颜色" type="color" @input="color(($event.target as HTMLInputElement).value)"></label></div>
    <label>透明度<input :value="item.style.opacity" aria-label="批注透明度" type="number" min="0.05" max="1" step="0.05" required @input="style('opacity',$event)"></label>
    <label v-if="['freeText','watermark'].includes(item.type)">字号 (pt)<input :value="item.style.fontSize" aria-label="批注字号" type="number" min="6" max="144" required @input="style('fontSize',$event)"></label>
    <label v-if="['ink','rectangle','circle','ellipse'].includes(item.type)">线宽 (pt)<input :value="item.style.lineWidth" aria-label="批注线宽" type="number" min="0.25" max="20" step="0.25" required @input="style('lineWidth',$event)"></label>
    <template v-if="['rectangle','circle','ellipse'].includes(item.type)"><label><input type="checkbox" aria-label="启用填充" :checked="!!item.style.fill" @change="emit('change',{...item,style:{...item.style,fill:($event.target as HTMLInputElement).checked ? item.color : null}})">填充</label><input v-if="item.style.fill" type="color" aria-label="填充颜色" :value="item.style.fill" @input="emit('change',{...item,style:{...item.style,fill:($event.target as HTMLInputElement).value}})"></template>
  </fieldset>
</template>
