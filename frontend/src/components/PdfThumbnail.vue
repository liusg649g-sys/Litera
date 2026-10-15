<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
const props = defineProps<{ pdf: PDFDocumentProxy; pageNumber: number; current: number }>()
const emit = defineEmits<{ navigate: [number] }>()
const host = ref<HTMLElement>(), canvas = ref<HTMLCanvasElement>(), height = ref(176), error = ref('')
let observer: IntersectionObserver | undefined, sizeObserver: ResizeObserver | undefined, resolution: MediaQueryList | undefined
let task: RenderTask | undefined, generation = 0, running = false, wanted = false, disposed = false, done = false, renderKey = ''
function dimensions() {
  const width = canvas.value?.getBoundingClientRect().width || 128
  const dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1))
  return { width, dpr, key: `${width}:${dpr}` }
}
async function render() {
  if (running || !wanted || disposed || done) return
  const token = ++generation; running = true
  const stage = document.createElement('canvas')
  try {
    const page = await props.pdf.getPage(props.pageNumber)
    if (token !== generation || disposed) return
    const original = page.getViewport({ scale: 1 }), size = dimensions()
    const viewport = page.getViewport({ scale: size.width / original.width })
    height.value = 128 * original.height / original.width
    // CSS keeps the original thumbnail size; only the backing store follows DPR.
    stage.width = Math.ceil(viewport.width * size.dpr); stage.height = Math.ceil(viewport.height * size.dpr)
    task = page.render({ canvas: stage, viewport, transform: [size.dpr, 0, 0, size.dpr, 0, 0] }); await task.promise
    if (token !== generation || disposed) return
    canvas.value!.width = stage.width; canvas.value!.height = stage.height
    canvas.value!.getContext('2d')!.drawImage(stage, 0, 0); done = true; error.value = ''
  } catch { if (token === generation && !disposed) error.value = '缩略图加载失败，点击仍可跳页' }
  finally { stage.width = stage.height = 0; task = undefined; running = false; if (wanted && token !== generation && !disposed) void render() }
}
function release() { generation++; task?.cancel(); if (canvas.value) canvas.value.width = canvas.value.height = 0; done = false }
function resize() {
  const key = dimensions().key
  if (key === renderKey) return
  renderKey = key; release(); if (wanted) void render()
}
function watchResolution() {
  resolution?.removeEventListener('change', resolutionChanged)
  resolution = matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`)
  resolution.addEventListener('change', resolutionChanged)
}
function resolutionChanged() { resize(); watchResolution() }
onMounted(() => {
  const root = host.value!.closest('.reader-panel')
  renderKey = dimensions().key
  sizeObserver = new ResizeObserver(resize); sizeObserver.observe(canvas.value!)
  watchResolution()
  observer = new IntersectionObserver(entries => { wanted = entries[0]!.isIntersecting; if (wanted) void render(); else release() }, { root, rootMargin: '150px 0px' }); observer.observe(host.value!)
})
onBeforeUnmount(() => { disposed = true; observer?.disconnect(); sizeObserver?.disconnect(); resolution?.removeEventListener('change', resolutionChanged); release() })
</script>
<template><button ref="host" class="pdf-thumbnail" :class="{ selected: current === pageNumber }" :aria-current="current === pageNumber ? 'page' : undefined" :aria-label="`缩略图第 ${pageNumber} 页`" @click="emit('navigate', pageNumber)"><canvas ref="canvas" width="0" height="0" :style="{ width: '128px', height: 'auto', aspectRatio: `128 / ${height}` }" /><span>{{ pageNumber }}</span><small v-if="error">{{ error }}</small></button></template>
