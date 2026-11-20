<script lang="ts">
let openCount = 0
let originalOverflow = ''
</script>
<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import GameIcon from './GameIcon.vue'
defineProps<{ title: string; subtitle?: string; wide?: boolean }>()
const emit = defineEmits<{ close: []; keydown: [event: KeyboardEvent] }>()
const sheet = ref<HTMLElement | null>(null)
const body = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null
// Teleport后的绘制顺序决定顶层；主城直达弟子详情时，子弹窗会先于父弹窗挂载。
function topModal() { return Array.from(document.querySelectorAll<HTMLElement>('[data-panel-modal]')).at(-1) }
function syncLayers() {
  const top = topModal()
  document.querySelectorAll<HTMLElement>('[data-panel-modal]').forEach(dialog => {
    dialog.inert = dialog !== top
    dialog.setAttribute('aria-modal', String(dialog === top))
  })
  return top
}
function resetScroll() { if (body.value) body.value.scrollTop = 0 }
defineExpose({ resetScroll })
function onKey(event: KeyboardEvent) {
  if (event.defaultPrevented || topModal() !== sheet.value) return
  if (event.key === 'Escape') { event.preventDefault(); emit('close') }
  if (event.key !== 'Tab' || !sheet.value) return
  const targets = Array.from(sheet.value.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')).filter(el => el.getClientRects().length > 0)
  const first = targets[0]; const last = targets.at(-1)
  if (!first || !last) { event.preventDefault(); sheet.value.focus(); return }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === sheet.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  else if (!sheet.value.contains(document.activeElement)) { event.preventDefault(); first.focus() }
}
onMounted(async () => {
  previousFocus = document.activeElement as HTMLElement | null
  if (openCount === 0) originalOverflow = document.body.style.overflow
  openCount += 1
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', onKey)
  await nextTick()
  if (syncLayers() === sheet.value) sheet.value?.focus({ preventScroll: true })
})
onUnmounted(() => {
  openCount -= 1
  if (openCount === 0) document.body.style.overflow = originalOverflow
  window.removeEventListener('keydown', onKey)
  const top = syncLayers()
  if (previousFocus?.isConnected && (!top || top.contains(previousFocus))) previousFocus.focus({ preventScroll: true })
  else top?.focus({ preventScroll: true })
})
</script>
<template><Teleport to="body"><div class="modal-overlay" @click.self="$emit('close')"><section ref="sheet" data-panel-modal class="modal-sheet" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1" @keydown="emit('keydown',$event)"><header class="modal-head"><div class="modal-heading"><svg class="modal-sigil" viewBox="0 0 36 46" fill="none" aria-hidden="true"><path d="M3 1h30v44H3zM7 5h22v36H7z" stroke="currentColor"/><path d="m18 11 7 11-7 12-7-12 7-11Zm-8 11h16M18 11v23" stroke="currentColor"/><path d="M1 9h5M30 37h5" stroke="currentColor" stroke-width="2"/></svg><div class="modal-titles"><span class="eyebrow">云岫仙宗 · {{ subtitle ?? '宗门事务' }}</span><h2>{{ title }}</h2></div></div><div class="modal-head-controls"><slot name="actions" /><button class="modal-close btn btn-quiet" aria-label="关闭面板" @click="$emit('close')"><GameIcon name="close" /></button></div></header><div ref="body" class="modal-body"><slot /></div></section></div></Teleport></template>
<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: clamp(12px, 3vw, 34px);
  background: #061510d9;
  backdrop-filter: blur(10px) saturate(.85);
  animation: veil-arrive .16s ease-out;
}
.modal-sheet {
  display: flex;
  flex-direction: column;
  width: min(860px, 100%);
  min-width: 0;
  max-height: min(90dvh, 960px);
  overflow: hidden;
  background: var(--surface);
  border: 1px solid #45665b;
  box-shadow: 0 30px 90px #030d0acc, 0 0 0 5px #102c2544;
  outline: 0;
  animation: sheet-unroll .2s cubic-bezier(.2,.7,.3,1);
}
.modal-sheet.wide { width: min(1160px, 100%); }
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 76px;
  padding: 15px 22px;
  border-top: 4px solid var(--jade);
  border-bottom: 1px solid var(--border);
  background: var(--surface-raised);
  flex: none;
}
.modal-head > div { min-width: 0; }
.modal-heading { display: flex; align-items: center; gap: 12px; }
.modal-sigil { width: 26px; height: 36px; color: var(--gold); flex: none; }
.modal-titles { min-width: 0; }
.modal-head .eyebrow { color: var(--gold); letter-spacing: .16em; }
.modal-head h2 { margin: 3px 0 0; color: var(--ink); font-size: 24px; letter-spacing: .06em; line-height: 1.4; overflow-wrap: anywhere; }
.modal-head-controls { display: flex; align-items: center; gap: 4px; flex: none; }
.modal-close { width: 42px; height: 42px; border: 1px solid transparent; color: var(--muted); }
.modal-close:hover { border-color: #53776a; background: #29443f; color: var(--ink); }
.modal-body {
  min-height: 0;
  overflow-y: auto;
  padding: 24px 26px 30px;
  background: var(--surface-inset);
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #55766a #14221f;
}
.modal-body :deep(.paper), .modal-body :deep(.panel) {
  box-shadow: none;
  border-color: var(--border);
}
@keyframes veil-arrive { from { background: #06151000; } }
@keyframes sheet-unroll { from { opacity: 0; transform: translateY(8px); } }
@media (max-width: 640px) {
  .modal-overlay { padding: 8px; align-items: stretch; }
  .modal-sheet { width: 100%; max-height: calc(100dvh - 16px); }
  .modal-head { min-height: 66px; padding: 12px 14px; gap: 10px; }
  .modal-heading { gap: 8px; }
  .modal-sigil { width: 21px; height: 30px; }
  .modal-head h2 { font-size: 20px; letter-spacing: .03em; }
  .modal-body { padding: 16px 12px 22px; }
}
@media (prefers-reduced-motion: reduce) { .modal-overlay, .modal-sheet { animation: none; } }
</style>
