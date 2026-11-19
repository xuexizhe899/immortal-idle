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
.modal-overlay{position:fixed;inset:0;z-index:40;padding:30px;background:#16362bb0;backdrop-filter:blur(5px);display:grid;place-items:center;animation:veil-arrive .16s ease-out}
.modal-sheet{display:flex;flex-direction:column;width:min(820px,100%);min-width:0;max-height:min(88dvh,950px);background:var(--surface);border:1px solid #d7caa5;box-shadow:0 28px 100px #0e201c66,inset 0 0 0 5px #e6deca;outline:0;animation:sheet-unroll .2s cubic-bezier(.2,.7,.3,1)}
.modal-sheet.wide{width:min(1100px,100%)}
.modal-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:17px 26px;border-top:3px solid var(--jade);border-bottom:1px solid var(--border);background:var(--surface-raised);box-shadow:0 3px 0 #b8aa7b12;flex:none}
.modal-head>div{min-width:0}
.modal-heading{display:flex;align-items:center;gap:14px}.modal-sigil{width:30px;height:40px;color:var(--gold);flex:none}.modal-titles{min-width:0}
.modal-head-controls{display:flex;align-items:center;gap:8px;flex:none}
.modal-head h2{margin:3px 0 0;font-size:25px;line-height:1.4;letter-spacing:.08em;overflow-wrap:anywhere}
.modal-body{padding:24px 26px;overflow-y:auto;min-height:0;overscroll-behavior:contain;scrollbar-gutter:stable;scrollbar-width:thin;scrollbar-color:#a4b091 #eee9d9}
.modal-close{flex:none;width:44px;height:44px;padding:8px}
@keyframes veil-arrive{from{background:#16362b00}}
@keyframes sheet-unroll{from{opacity:0;transform:translateY(8px)}}
@media(max-width:640px){
  .modal-overlay{padding:10px;align-items:stretch}
  .modal-sheet{max-height:calc(100dvh - 20px);width:100%}
  .modal-head{padding:16px;gap:10px}
  .modal-heading{gap:9px}.modal-sigil{width:23px;height:34px}
  .modal-head h2{font-size:22px}
  .modal-body{padding:18px 14px}
  .modal-head .eyebrow{font-size:8px}
  .modal-close{width:44px;height:44px}
}
@media(prefers-reduced-motion:reduce){.modal-overlay,.modal-sheet{animation:none}}
</style>
