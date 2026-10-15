<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Close } from '@element-plus/icons-vue'
import { readerTabs, moveReaderTab } from '../reader/state'
const route = useRoute(), router = useRouter()
const activeId = computed(() => route.path.startsWith('/reader/') ? String(route.params.documentId) : '')
const bar = ref<HTMLElement>(), tooltipId = ref(''), dragging = ref(''), beforeId = ref<string | null>(null)
let tooltipTimer: ReturnType<typeof setTimeout> | undefined, stopDrag: (() => void) | undefined
let suppressClickUntil = 0
function hideTooltip() { clearTimeout(tooltipTimer); tooltipId.value = '' }
function showTooltip(id: string, event: Event) {
  hideTooltip()
  const text = (event.currentTarget as HTMLElement).querySelector<HTMLElement>('.cell-text')
  if (!dragging.value && text && text.scrollWidth > text.clientWidth + 1) {
    tooltipTimer = setTimeout(() => { tooltipId.value = id }, 100)
  }
}
function leaveTooltip() {
  clearTimeout(tooltipTimer)
  tooltipTimer = setTimeout(() => { tooltipId.value = '' }, 100)
}
function activate(id: string, event: MouseEvent) {
  if (event.detail > 0 && performance.now() < suppressClickUntil) { suppressClickUntil = 0; return }
  hideTooltip(); void router.push(`/reader/${id}`)
}
function startDrag(event: PointerEvent, id: string) {
  if (event.button !== 0 || event.pointerType !== 'mouse') return
  stopDrag?.(); hideTooltip(); suppressClickUntil = 0
  const source = event.currentTarget as HTMLElement, startX = event.clientX, startY = event.clientY
  let x = startX, y = startY, frame = 0
  function inside() {
    const rect = bar.value!.getBoundingClientRect()
    const home = bar.value!.querySelector('.workspace-home')!.getBoundingClientRect()
    return x >= home.right && x <= rect.right && y >= rect.top && y <= rect.bottom
  }
  function locate() {
    const targets = [...bar.value!.querySelectorAll<HTMLElement>('.reader-tab')].filter(tab => tab.dataset.tabId !== id)
    beforeId.value = targets.find(tab => { const rect = tab.getBoundingClientRect(); return x < rect.x + rect.width / 2 })?.dataset.tabId ?? null
  }
  function tick() {
    if (inside()) {
      const rect = bar.value!.getBoundingClientRect()
      const home = bar.value!.querySelector('.workspace-home')!.getBoundingClientRect()
      const delta = x > rect.right - 32 ? 9 : x < home.right + 32 ? -9 : 0
      if (delta) bar.value!.scrollLeft += delta
      locate()
    }
    frame = requestAnimationFrame(tick)
  }
  function move(e: PointerEvent) {
    if (e.pointerId !== event.pointerId) return
    x = e.clientX; y = e.clientY
    if (!dragging.value && Math.abs(x - startX) >= 6 && Math.abs(x - startX) > Math.abs(y - startY)) {
      dragging.value = id; hideTooltip(); source.setPointerCapture(event.pointerId); tick()
    }
    if (dragging.value) { e.preventDefault(); locate() }
  }
  function finish(e?: PointerEvent) {
    if (e && e.pointerId !== event.pointerId) return
    if (dragging.value) {
      suppressClickUntil = performance.now() + 300
      if (e?.type === 'pointerup' && inside()) { locate(); moveReaderTab(id, beforeId.value) }
    }
    cleanup()
  }
  function key(e: KeyboardEvent) { if (e.key === 'Escape') { e.preventDefault(); finish() } }
  function cleanup() {
    cancelAnimationFrame(frame)
    window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish)
    window.removeEventListener('pointercancel', finish); window.removeEventListener('keydown', key); window.removeEventListener('blur', cancel)
    source.removeEventListener('lostpointercapture', cancel)
    if (source.hasPointerCapture(event.pointerId)) source.releasePointerCapture(event.pointerId)
    dragging.value = ''; beforeId.value = null; stopDrag = undefined
  }
  function cancel() { finish() }
  window.addEventListener('pointermove', move, { passive: false }); window.addEventListener('pointerup', finish)
  window.addEventListener('pointercancel', finish); window.addEventListener('keydown', key); window.addEventListener('blur', cancel)
  source.addEventListener('lostpointercapture', cancel)
  stopDrag = cancel
}
onBeforeUnmount(() => { stopDrag?.(); hideTooltip() })
async function close(id: string) {
  let index = readerTabs.findIndex(tab => tab.id === id)
  if (index < 0) return
  if (activeId.value === id) {
    const next = readerTabs[index + 1] || readerTabs[index - 1]
    const failure = await router.push(next ? `/reader/${next.id}` : '/library')
    if (failure) return
  }
  index = readerTabs.findIndex(tab => tab.id === id)
  if (index >= 0) readerTabs.splice(index, 1)
}
</script>
<template>
  <nav v-if="readerTabs.length" ref="bar" class="workspace-tabs reader-tabs" :class="{ 'is-dragging': dragging }" aria-label="已打开文献">
    <router-link class="workspace-home" :class="{ active: !activeId }" to="/library" :aria-current="!activeId ? 'page' : undefined">文献管理</router-link>
    <div v-for="(tab, index) in readerTabs" :key="tab.id" class="reader-tab" :data-tab-id="tab.id" :class="{ active: activeId === tab.id, dragging: dragging === tab.id, 'drop-before': dragging && beforeId === tab.id, 'drop-after': dragging && beforeId === null && index === readerTabs.length - 1 }">
      <el-tooltip :content="tab.title" :visible="tooltipId === tab.id && !dragging" :show-after="100" :hide-after="100" :enterable="false" transition="" effect="light" popper-class="library-popover workspace-title-tooltip" placement="bottom" :popper-options="{ strategy: 'fixed' }">
        <button type="button" class="overflow-text document-title" :aria-pressed="activeId === tab.id" @mouseenter="showTooltip(tab.id, $event)" @mouseleave="leaveTooltip" @focus="showTooltip(tab.id, $event)" @blur="hideTooltip" @pointerdown="startDrag($event, tab.id)" @click="activate(tab.id, $event)"><span class="cell-text">{{ tab.title }}</span></button>
      </el-tooltip>
      <button class="workspace-tab-close" :aria-label="`关闭文献：${tab.title}`" @click="close(tab.id)"><Close /></button>
    </div>
  </nav>
</template>
<style scoped>
.workspace-tabs { display:flex; overflow-x:auto; height:var(--litera-tabs-height); min-height:var(--litera-tabs-height); flex-shrink:0; background:var(--litera-page); border-bottom:1px solid var(--litera-border); font-size:var(--litera-font-size-ui); scrollbar-width:none }
.workspace-tabs::-webkit-scrollbar { display:none }
.workspace-home { position:sticky; left:0; z-index:2; background:var(--litera-page); display:flex; align-items:center; flex-shrink:0; padding:0 18px; border-right:1px solid var(--litera-border); border-top:2px solid transparent; color:var(--litera-muted); text-decoration:none }
.reader-tab { display:flex; align-items:center; width:240px; min-width:170px; flex-shrink:0; padding:0 6px 0 12px; border-right:1px solid var(--litera-border); border-top:2px solid transparent }
.workspace-home.active,.reader-tab.active { background:var(--litera-card); border-top-color:var(--litera-primary); color:var(--litera-primary) }
.reader-tab :deep(.overflow-text) { flex:1; min-width:0; display:flex; justify-content:flex-start; text-align:left; border:0; background:transparent; color:inherit; font:inherit; cursor:pointer; padding:8px 0 }
.reader-tab :deep(.cell-text) { overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
.workspace-tab-close { padding:5px; border:0; background:transparent; color:var(--litera-muted); cursor:pointer; display:flex; border-radius:4px }
.workspace-tab-close:hover { background:var(--litera-border) }
.workspace-tab-close svg { width:14px; height:14px }
.reader-tab.dragging { opacity:.55 }
.reader-tab.drop-before { box-shadow:inset 3px 0 var(--litera-primary) }
.reader-tab.drop-after { box-shadow:inset -3px 0 var(--litera-primary) }
.reader-tab .overflow-text { user-select:none; touch-action:pan-y }
.is-dragging .overflow-text { cursor:grabbing }
</style>
