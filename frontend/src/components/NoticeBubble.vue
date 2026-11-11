<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import GameIcon from './GameIcon.vue'

const props = withDefaults(defineProps<{
  tone?: 'notice' | 'error' | 'busy'
  message: string
  noticeId?: number
  duration?: number
}>(), { tone: 'notice', noticeId: 0, duration: 5000 })
const emit = defineEmits<{ close: [] }>()
const root = ref<HTMLElement | null>(null)
const hovered = ref(false)
const focused = ref(false)
let timer: number | undefined

const seal = computed(() => props.tone === 'error' ? '戒' : props.tone === 'busy' ? '候' : '讯')
const dismissible = computed(() => props.tone !== 'busy')
const liveRole = computed(() => props.tone === 'error' ? 'alert' : 'status')
const closeLabel = computed(() => props.tone === 'error' ? '关闭错误提示' : '关闭提示')

function clearTimer() {
  if (timer === undefined) return
  window.clearTimeout(timer)
  timer = undefined
}
function schedule() {
  clearTimer()
  if (props.tone !== 'notice' || hovered.value || focused.value) return
  timer = window.setTimeout(() => emit('close'), props.duration)
}
function syncPause() {
  if (hovered.value || focused.value) clearTimer()
  else schedule()
}
function setHovered(value: boolean) { hovered.value = value; syncPause() }
function setFocused(value: boolean) { focused.value = value; syncPause() }
function onFocusOut(event: FocusEvent) {
  const next = event.relatedTarget as Node | null
  if (next && root.value?.contains(next)) return
  setFocused(false)
}
// 相同文案再次提示时 noticeId 会变化，同样重新出现并重新计时。
watch([() => props.message, () => props.noticeId], schedule, { immediate: true })
onBeforeUnmount(clearTimer)
</script>
<template>
  <div ref="root" class="notice-bubble" :class="`tone-${tone}`" @mouseenter="setHovered(true)" @mouseleave="setHovered(false)" @focusin="setFocused(true)" @focusout="onFocusOut">
    <span class="bubble-avatar" aria-hidden="true">{{ seal }}</span>
    <div class="bubble-surface">
      <span class="bubble-tail" aria-hidden="true"></span>
      <div class="bubble-head">
        <p class="bubble-text" :role="liveRole" :aria-live="tone === 'error' ? 'assertive' : 'polite'" aria-atomic="true">{{ message }}<span v-if="tone === 'busy'" class="busy-dots" aria-hidden="true"><i></i><i></i><i></i></span></p>
        <button v-if="dismissible" type="button" class="bubble-close" :aria-label="closeLabel" @click="emit('close')"><GameIcon name="close" /></button>
      </div>
      <div v-if="$slots.default" class="bubble-actions"><slot /></div>
    </div>
  </div>
</template>
<style scoped>
.notice-bubble {
  --bubble-bg: #f5f7e8; --bubble-border: #a9b996; --bubble-ink: #2d5644;
  --seal-ink: #3c6b56; --seal-border: #93a787; --seal-bg: #faf5e5;
  position: relative; display: flex; align-items: flex-end; gap: 9px;
  flex: none; max-width: 100%; color: var(--bubble-ink); pointer-events: auto;
}
.tone-error {
  --bubble-bg: #faecdf; --bubble-border: #c99580; --bubble-ink: #8f4032;
  --seal-ink: #a44e3f; --seal-border: #b26955; --seal-bg: #fbf1e7;
}
.tone-busy {
  --bubble-bg: #f5f0e1; --bubble-border: #bdb08d; --bubble-ink: #40544a;
  --seal-ink: #5c745f; --seal-border: #a6ab8e; --seal-bg: #faf5e5;
}
.bubble-avatar {
  flex: none; display: grid; place-items: center; width: 36px; height: 38px; margin-bottom: 1px;
  border: 1px solid var(--seal-border); background: var(--seal-bg);
  box-shadow: inset 0 0 0 2px var(--bubble-bg), inset 0 0 0 3px var(--seal-border), 0 2px 0 #26382f14;
  font: 19px 'SimSun', 'STSong', serif; line-height: 1; color: var(--seal-ink);
}
.bubble-surface {
  position: relative; min-width: 0; padding: 11px 12px 11px 14px;
  border: 1px solid var(--bubble-border); background: var(--bubble-bg);
  box-shadow: inset 0 0 0 2px #fffdf5b8, 0 3px 0 #6f7b6826, 0 10px 26px #26382f1f;
}
.bubble-tail {
  position: absolute; left: -7px; bottom: 13px; width: 12px; height: 12px;
  background: var(--bubble-bg); border-left: 1px solid var(--bubble-border);
  border-bottom: 1px solid var(--bubble-border); transform: rotate(45deg);
}
.bubble-head { display: flex; align-items: flex-start; gap: 8px; }
.bubble-text { flex: 1; min-width: 0; margin: 0; font-size: 13px; line-height: 1.7; letter-spacing: .01em; overflow-wrap: anywhere; }
.bubble-close {
  flex: none; display: grid; place-items: center; width: 26px; height: 26px; margin: -4px -4px 0 0;
  padding: 4px; border: 0; background: transparent; color: var(--bubble-ink); opacity: .58;
  transition: opacity .15s, background .15s;
}
.bubble-close:hover { opacity: 1; background: #ffffff66; }
.bubble-close .game-icon { width: 15px; height: 15px; }
.bubble-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.bubble-actions :deep(.btn) { min-height: 30px; padding: 4px 11px; font-size: 11px; }
.busy-dots { display: inline-flex; gap: 3px; margin-left: 7px; vertical-align: 1px; }
.busy-dots i { width: 3px; height: 3px; background: currentColor; opacity: .3; animation: bubble-dot 1.1s infinite; }
.busy-dots i:nth-child(2) { animation-delay: .16s; }
.busy-dots i:nth-child(3) { animation-delay: .32s; }
@keyframes bubble-dot { 0%, 65%, 100% { opacity: .25; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-2px); } }
@media(max-width:640px) {
  .bubble-avatar { width: 33px; height: 35px; font-size: 17px; }
  .bubble-surface { padding: 10px 11px 10px 13px; }
  .bubble-text { font-size: 13px; }
  .bubble-close { width: 36px; height: 36px; margin: -5px -5px 0 0; }
  .bubble-actions :deep(.btn) { min-height: 36px; }
}
@media (prefers-reduced-motion: reduce) {
  .busy-dots i { animation: none; opacity: .65; transform: none; }
}
</style>
