<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import GameIcon from './components/ui/GameIcon.vue'
import NoticeBubble from './components/ui/NoticeBubble.vue'
import { number } from './shared/format'
import { useGameStore } from './stores/game'
import CityView from './views/CityView.vue'
import RunView from './views/RunView.vue'
const store = useGameStore()
const inRun = computed(() => store.status !== 'idle')
// Browsing the sect changes only the screen; the server keeps the expedition.
const viewingCity = ref(false)
const cityMode = computed(() => !!store.state && (!inRun.value || viewingCity.value))
watch([() => store.slotId, () => store.state?.active_run?.run_seed], () => { viewingCity.value = false })
const currentSave = computed(() => store.saves.find(save => save.slot_id === store.slotId))
const runLocation = computed(() => {
  const run = store.state?.active_run
  if (!run) return '山中岁月，自有所得'
  if (run.practice) return '阵容演练中'
  if (run.world_node_id) return String(run.party_snapshot?.mode.world_node && (run.party_snapshot.mode.world_node as Record<string, unknown>).name || '山河历练中')
  return run.sect_id ? '宗门征讨中' : run.mode === 'expedition' ? '远行中' : '问道塔出征中'
})
const resources = [{ key: 'cultivation', label: '修为', icon: 'leaf' }, { key: 'spirit_stone', label: '灵石', icon: 'stone' }, { key: 'stamina', label: '行动力', icon: 'flame' }, { key: 'reputation', label: '声望', icon: 'star' }] as const
const busyMessage = computed(() => store.operation ? `正在${store.operation}` : '正在处理')
const saveStatus = computed(() => store.error ? '进度待确认' : store.busy ? '正在同步' : store.state ? '存档已载入' : '正在载入')
onMounted(() => { void store.bootstrap() })
</script>
<template>
  <div class="game-shell" :class="{ 'city-mode': cityMode }">
    <header class="game-header">
      <div class="brand"><span class="brand-seal">道</span><div><h1>云岫仙宗</h1><span class="brand-sub">山海有灵 · 问道长生</span></div></div>
      <div class="resource-hud" aria-label="已入账宗门资源"><div v-for="item in resources" :key="item.key" class="hud-item" :data-resource="item.key"><span class="hud-icon"><GameIcon :name="item.icon" /></span><div><span class="hud-label">{{ item.label }}<small v-if="item.key !== 'reputation'" class="hud-rate">+{{ number(store.production[item.key],1) }}/时</small></span><strong :key="`${store.slotId}:${store.resources?.[item.key] ?? 0}`" :title="number(store.resources?.[item.key],2)">{{ number(store.resources?.[item.key], item.key === 'stamina' ? 1 : 0) }}</strong></div></div></div>
      <div class="save-indicator" :class="{ pending: store.busy, uncertain: !!store.error }"><span class="save-state"><span class="status-dot" aria-hidden="true"></span>{{ saveStatus }}</span><strong>{{ currentSave?.name ?? '宗门存档' }}</strong><small>{{ runLocation }}</small></div>
    </header>
    <main class="game-main">
      <div v-if="!store.state" class="boot-screen" :class="{ failed: !!store.error }" :aria-busy="!store.error"><span class="boot-seal" aria-hidden="true">仙</span><h2>{{ store.error ? '山门暂未开启' : '正在叩开山门' }}</h2><p class="muted">{{ store.error ?? '整理宗门典籍，片刻便好…' }}</p><button v-if="store.error" class="btn btn-primary" :disabled="store.busy" @click="store.bootstrap()">重新尝试</button></div>
      <template v-else><CityView v-if="!inRun || viewingCity" @resume-run="viewingCity = false" /><RunView v-else @return-city="viewingCity = true" /></template>
    </main>
    <Teleport to="body">
      <div class="feedback-dock" :class="{ 'above-city-dock': cityMode }">
        <Transition name="bubble">
          <NoticeBubble v-if="store.error && store.state" key="error" tone="error" :message="store.error ?? ''" @close="store.clearError()">
            <button class="btn btn-small" :disabled="store.busy" @click="store.refresh()">刷新状态</button>
          </NoticeBubble>
        </Transition>
        <Transition name="bubble">
          <NoticeBubble v-if="!store.error && store.notice && store.state" key="notice" tone="notice" :message="store.notice ?? ''" :notice-id="store.noticeId" @close="store.dismissNotice()" />
        </Transition>
        <Transition name="bubble">
          <NoticeBubble v-if="store.busy" key="busy" tone="busy" :message="busyMessage" />
        </Transition>
      </div>
    </Teleport>
  </div>
</template>
<style scoped>
.game-shell { min-height: 100dvh; background: radial-gradient(ellipse at 50% 35%, #f7f2df 0, #e1e5d5 65%, #ccd4c3 100%); }
.city-mode { height: 100dvh; display: flex; flex-direction: column; overflow: hidden; }
.city-mode .game-header { flex: none; }
.city-mode .game-main { flex: 1; min-height: 0; }
.feedback-dock.above-city-dock { --feedback-bottom: calc(190px + env(safe-area-inset-bottom)); }
.game-header { position: relative; z-index: 5; min-height: 86px; display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 12px 34px; border-top: 3px solid #355d48; border-bottom: 1px solid #adad8b; background: #f6f1e2; box-shadow: 0 3px 0 #fdf8e8, 0 5px 18px #3b523518; }
.brand { display: flex; align-items: center; gap: 12px; min-width: 200px; }.brand-seal { width: 43px; height: 47px; display: grid; place-items: center; border: 1px solid #9b7b49; box-shadow: inset 0 0 0 3px #f5f0e1, inset 0 0 0 4px #9b7b49; font: 25px 'SimSun',serif; color: #96622f; }
.brand h1 { margin: 0; font-size: 24px; letter-spacing: .18em; line-height: 1.35; }.brand-sub { font-size: 10px; letter-spacing: .16em; color: var(--muted); }
.resource-hud { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: clamp(14px,2.8vw,46px); min-width: 0; }.hud-item { --resource-ink: #326c55; display: flex; align-items: center; gap: 9px; min-width: 0; }.hud-item[data-resource="spirit_stone"] { --resource-ink: #4b7c7d; }.hud-item[data-resource="stamina"] { --resource-ink: #9b7140; }.hud-item[data-resource="reputation"] { --resource-ink: #886448; }.hud-icon { display: grid; place-items: center; width: 35px; height: 39px; flex: none; color: var(--resource-ink); border: 1px solid #c3c3a5; background: #e8e9d6; box-shadow: inset 0 0 0 3px #f5f1df; }.hud-item .game-icon { width: 22px; height: 22px; }.hud-item div { display: flex; flex-direction: column; min-width: 0; }.hud-label { display: flex; align-items: baseline; gap: 6px; white-space: nowrap; color: var(--muted); font-size: 10px; }.hud-rate { font-size: 9px; color: #6d7e69; }.hud-item strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 20px; line-height: 1.4; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--ink); animation: resource-ink .42s ease-out; }
.save-indicator { font-size: 12px; text-align: right; color: var(--jade); min-width: 140px; max-width: 200px; }.save-state { display: block; margin-bottom: 2px; font-size: 9px; color: #658168; }.save-indicator strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 500; }.save-indicator small { display: block; color: var(--muted); font-size: 10px; }.status-dot { display: inline-block; width: 5px; height: 5px; background: var(--jade); margin-right: 7px; transform: rotate(45deg); }.pending .save-state { color: #92733d; }.pending .status-dot { background: #b38a46; }.uncertain .save-state { color: var(--danger); }.uncertain .status-dot { background: var(--danger); }
.game-main { min-height: calc(100dvh - 86px); }.boot-screen { min-height: 70dvh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 30px; text-align: center; }.boot-seal { font: 70px 'SimSun',serif; color: var(--jade); margin-bottom: 20px; }
.boot-seal { display: grid; place-items: center; width: 108px; height: 120px; border: 1px solid #9daa82; box-shadow: inset 0 0 0 6px var(--surface), inset 0 0 0 7px #aeb993, 0 12px 32px #40553f14; background: #eef0db; font-size: 58px; animation: boot-breathe 1.8s ease-in-out infinite; }.failed .boot-seal { animation: none; color: var(--wood); border-color: var(--wood); }
@keyframes resource-ink { from { background-color: #dfc88b70; } to { background-color: transparent; } }
@keyframes boot-breathe { 50% { opacity: .6; } }
.feedback-dock { --feedback-bottom: calc(22px + env(safe-area-inset-bottom)); position: fixed; z-index: 70; right: max(22px, env(safe-area-inset-right)); bottom: var(--feedback-bottom); display: flex; flex-direction: column; align-items: flex-end; gap: 9px; width: min(420px, calc(100vw - 32px)); max-height: calc(100dvh - var(--feedback-bottom) - 16px); padding: 8px; overflow-y: auto; overscroll-behavior: contain; pointer-events: none; }
@media(max-width: 1050px) { .save-indicator { min-width: 100px; max-width: 120px; }.save-indicator small { display: none; }.game-header { padding-inline: 22px; gap: 16px; }.brand { min-width: 170px; }.resource-hud { gap: 14px; flex: 1; }.hud-rate { display: none; } }
@media(min-width:641px) and (max-width:850px) { .brand { min-width: 150px; }.brand h1 { font-size: 22px; }.hud-icon { width: 25px; height: 31px; }.hud-item { gap: 6px; }.hud-item .game-icon { width: 17px; height: 17px; }.hud-item strong { font-size: 16px; } }
@media(max-width: 640px) { .game-header { padding: 12px 16px 10px; flex-wrap: wrap; gap: 10px; min-height: 126px; }.brand { width: 100%; justify-content: center; }.brand-seal { width: 30px; height: 34px; font-size: 20px; }.brand h1 { font-size: 20px; }.brand-sub { display: none; }.resource-hud { width: 100%; gap: 0; justify-content: space-between; }.hud-item { gap: 5px; }.hud-item .game-icon { width: 17px; height: 17px; }.hud-item strong { font-size: 15px; }.hud-item span { font-size: 9px; }.game-main { min-height: calc(100dvh - 126px); }.feedback-dock { --feedback-bottom: calc(96px + env(safe-area-inset-bottom)); left: 12px; right: 12px; width: auto; gap: 8px; } }
@media(max-width:640px) { .brand { order: 0; width: auto; min-width: 0; flex: 1; justify-content: flex-start; }.save-indicator { order: 1; min-width: 0; max-width: 44%; }.save-indicator strong { font-size: 10px; }.save-state { font-size: 9px; }.hud-icon { width: 25px; height: 31px; box-shadow: inset 0 0 0 2px #f5f1df; }.hud-label { gap: 3px; }.hud-rate { display: none; }.resource-hud { order: 2; gap: 6px; flex: none; }.hud-item { gap: 6px; } }
@media(prefers-reduced-motion:reduce) { .hud-item strong, .boot-seal { animation: none; } }
</style>
