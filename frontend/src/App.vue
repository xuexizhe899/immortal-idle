<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import GameIcon from './components/GameIcon.vue'
import { number } from './components/gameDisplay'
import { useGameStore } from './stores/game'
import CityView from './views/CityView.vue'
import RunView from './views/RunView.vue'
const store = useGameStore()
const inRun = computed(() => store.status !== 'idle')
// Browsing the sect changes only the screen; the server keeps the expedition.
const viewingCity = ref(false)
watch([() => store.slotId, () => store.state?.active_run?.run_seed], () => { viewingCity.value = false })
const currentSave = computed(() => store.saves.find(save => save.slot_id === store.slotId))
const resources = [{ key: 'cultivation', label: '修为', icon: 'leaf' }, { key: 'spirit_stone', label: '灵石', icon: 'stone' }, { key: 'stamina', label: '行动力', icon: 'flame' }, { key: 'reputation', label: '声望', icon: 'star' }] as const
onMounted(() => { void store.bootstrap() })
</script>
<template>
  <div class="game-shell">
    <header class="game-header">
      <div class="brand"><span class="brand-seal">道</span><div><h1>云岫仙宗</h1><span class="brand-sub">山海有灵 · 问道长生</span></div></div>
      <div class="resource-hud" aria-label="宗门资源"><div v-for="item in resources" :key="item.key" class="hud-item"><GameIcon :name="item.icon" /><div><span>{{ item.label }}</span><strong>{{ number(store.resources?.[item.key], item.key === 'stamina' ? 1 : 0) }}</strong></div></div></div>
      <div class="save-indicator"><span class="status-dot"></span>{{ currentSave?.name ?? '宗门存档' }}<small>{{ inRun ? '问道塔出征中' : '山中岁月，自有所得' }}</small></div>
    </header>
    <main class="game-main">
      <div v-if="!store.state" class="boot-screen"><span class="boot-seal">仙</span><h2>{{ store.error ? '山门暂未开启' : '正在叩开山门' }}</h2><p class="muted">{{ store.error ?? '整理宗门典籍，片刻便好…' }}</p><button v-if="store.error" class="btn btn-primary" @click="store.bootstrap()">重新尝试</button></div>
      <template v-else><CityView v-if="!inRun || viewingCity" @resume-run="viewingCity = false" /><RunView v-else @return-city="viewingCity = true" /></template>
    </main>
    <div v-if="store.busy" class="working-indicator" role="status"><span></span> 正在处理</div>
    <div v-if="store.error && store.state" class="global-message error-box" role="alert"><span>{{ store.error }}</span><button class="btn btn-small" :disabled="store.busy" @click="store.refresh()">刷新状态</button></div>
    <div v-else-if="store.notice" class="global-message notice-box" role="status"><span>{{ store.notice }}</span><button class="btn btn-small btn-quiet" aria-label="关闭提示" @click="store.dismissNotice()"><GameIcon name="close" /></button></div>
  </div>
</template>
<style scoped>
.game-shell { min-height: 100dvh; background: radial-gradient(ellipse at 50% 35%, #f7f2df 0, #e1e5d5 65%, #ccd4c3 100%); }
.game-header { position: relative; z-index: 5; min-height: 86px; display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 14px 34px; border-bottom: 1px solid #b3b99d; background: #f5f0e1f5; box-shadow: 0 3px 16px #3b523511; }
.brand { display: flex; align-items: center; gap: 12px; min-width: 200px; }.brand-seal { width: 43px; height: 47px; display: grid; place-items: center; border: 1px solid #9b7b49; box-shadow: inset 0 0 0 3px #f5f0e1, inset 0 0 0 4px #9b7b49; font: 25px 'SimSun',serif; color: #96622f; }
.brand h1 { margin: 0; font-size: 24px; letter-spacing: .18em; line-height: 1.35; }.brand-sub { font-size: 10px; letter-spacing: .16em; color: var(--muted); }
.resource-hud { display: flex; justify-content: center; gap: clamp(20px,4vw,70px); }.hud-item { display: flex; align-items: center; gap: 10px; }.hud-item .game-icon { color: var(--gold); width: 23px; height: 23px; }.hud-item div { display: flex; flex-direction: column; }.hud-item span { color: var(--muted); font-size: 10px; }.hud-item strong { font-size: 19px; line-height: 1.4; font-variant-numeric: tabular-nums; font-weight: 600; }
.save-indicator { font-size: 12px; text-align: right; color: var(--jade); min-width: 160px; }.save-indicator small { display: block; color: var(--muted); font-size: 10px; }.status-dot { display: inline-block; width: 5px; height: 5px; background: var(--jade); margin-right: 7px; }
.game-main { min-height: calc(100dvh - 86px); }.boot-screen { min-height: 70dvh; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 30px; text-align: center; }.boot-seal { font: 70px 'SimSun',serif; color: var(--jade); margin-bottom: 20px; }
.working-indicator { position: fixed; z-index: 60; bottom: 12px; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; align-items: center; padding: 6px 14px; background: #233d34e8; color: #f6f0da; font-size: 11px; pointer-events: none; }.working-indicator span { width: 6px; height: 6px; background: #c4ad6c; animation: blink 1s infinite alternate; }
.global-message { position: fixed; z-index: 55; bottom: 24px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 32px); display: flex; align-items: center; justify-content: space-between; gap: 18px; box-shadow: var(--shadow); }
@keyframes blink { to { opacity: .3; } }
@media(max-width: 1050px) { .save-indicator { display: none; }.game-header { padding-inline: 22px; }.resource-hud { gap: 26px; } }
@media(max-width: 640px) { .game-header { padding: 12px 16px 10px; flex-wrap: wrap; gap: 10px; min-height: 126px; }.brand { width: 100%; justify-content: center; }.brand-seal { width: 30px; height: 34px; font-size: 20px; }.brand h1 { font-size: 20px; }.brand-sub { display: none; }.resource-hud { width: 100%; gap: 0; justify-content: space-between; }.hud-item { gap: 5px; }.hud-item .game-icon { width: 17px; height: 17px; }.hud-item strong { font-size: 15px; }.hud-item span { font-size: 9px; }.game-main { min-height: calc(100dvh - 126px); }.global-message { bottom: 18px; font-size: 12px; } }
</style>
