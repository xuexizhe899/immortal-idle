<script setup lang="ts">
import CityNavIcon from './CityNavIcon.vue'
defineProps<{ towerLabel: string; towerHint: string; expeditionLabel: string; expeditionHint: string; discipleCount: number; dutyCount: number; active: string | null }>()
defineEmits<{ open: [panel: string] }>()
const entries = [{ id: 'sect', label: '宗门', hint: '设施 · 存档' }, { id: 'codex', label: '弟子', hint: '修炼 · 招贤' }, { id: 'duty', label: '值守', hint: '同道守山' }, { id: 'alchemy', label: '炼丹', hint: '丹火养元' }, { id: 'forge', label: '炼器', hint: '百炼成器' }, { id: 'expedition', label: '山河', hint: '寻器 · 守山' }, { id: 'tower', label: '问道', hint: '登塔试炼' }]
</script>
<template>
  <nav class="city-dock" aria-label="宗门功能">
    <div class="dock-inner">
      <button v-for="entry in entries" :key="entry.id" :class="['dock-entry', { 'dock-tower': entry.id === 'tower', 'dock-expedition': entry.id === 'expedition', selected: active === entry.id }]" :aria-current="active === entry.id ? 'page' : undefined" :aria-label="entry.id === 'tower' ? `${towerLabel}，${towerHint}` : entry.id === 'expedition' ? `${expeditionLabel}，${expeditionHint}` : entry.label" @click="$emit('open', entry.id)">
        <span class="dock-icon"><CityNavIcon :name="entry.id" /><span v-if="entry.id === 'codex' && discipleCount" class="dock-count">{{ discipleCount }}</span><i v-if="(entry.id === 'tower' && towerLabel !== '问道') || (entry.id === 'expedition' && expeditionLabel !== '山河')" class="run-dot"></i></span>
        <span class="dock-label">{{ entry.id === 'tower' ? towerLabel : entry.id === 'expedition' ? expeditionLabel : entry.label }}</span>
        <small :title="entry.id === 'tower' ? towerHint : entry.id === 'expedition' ? expeditionHint : entry.id === 'duty' ? `${dutyCount} 位值守` : entry.hint">{{ entry.id === 'tower' ? towerHint : entry.id === 'expedition' ? expeditionHint : entry.id === 'duty' ? `${dutyCount} 位值守` : entry.hint }}</small>
      </button>
    </div>
  </nav>
</template>
<style scoped>
.city-dock {
  position: relative;
  z-index: 10;
  flex: none;
  padding: 0 24px env(safe-area-inset-bottom);
  border-top: 1px solid #49665a;
  background: #102a23;
  box-shadow: 0 -8px 26px #07171066;
}
.dock-inner { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 2px; max-width: 1120px; margin: auto; }
.dock-entry {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 0;
  min-height: 82px;
  padding: 7px 5px 8px;
  border: 0;
  border-top: 2px solid transparent;
  background: transparent;
  color: #aabca8;
  transition: background .16s, color .16s, border-color .16s;
}
.dock-entry:hover, .dock-entry.selected { background: #1b3d32; color: #eef2e7; }
.dock-entry.selected { border-top-color: var(--jade); }
.dock-icon { position: relative; display: block; width: 34px; height: 34px; color: #83b8a0; opacity: .82; transition: opacity .16s; }
.dock-icon svg { width: 100%; height: 100%; }
.dock-entry:hover .dock-icon, .dock-entry.selected .dock-icon { opacity: 1; }
.dock-label { overflow: hidden; max-width: 100%; font: 600 14px/1.45 'Microsoft YaHei', 'PingFang SC', sans-serif; white-space: nowrap; text-overflow: ellipsis; }
.dock-entry small { overflow: hidden; max-width: 100%; color: #789282; font-size: 10px; white-space: nowrap; text-overflow: ellipsis; }
.dock-entry.selected small { color: #b6cda8; }
.dock-count { position: absolute; top: -2px; right: -6px; display: grid; place-items: center; min-width: 18px; height: 18px; padding: 0 4px; border: 1px solid #102a23; background: var(--gold); color: #20352c; font-size: 10px; line-height: 1; }
.dock-tower { border-top-color: #806c3f; }
.dock-tower:hover, .dock-tower.selected { background: #38351f; }
.dock-tower.selected { border-top-color: var(--gold); }
.dock-tower .dock-icon { color: var(--gold); }
.dock-tower .dock-label { color: #ebd58d; }
.dock-tower small { color: #b7a671; }
.dock-expedition .dock-icon { color: #86bda0; }
.run-dot { position: absolute; top: 1px; right: -2px; width: 8px; height: 8px; border: 2px solid #102a23; background: #e19c6a; }
.dock-entry:active { background: #24503f; }
.dock-entry:focus-visible { outline: 2px solid var(--gold); outline-offset: -4px; }
@media (hover: hover) and (pointer: fine) { .dock-entry:hover .dock-icon { transform: translateY(-1px); } }
@media (max-width: 640px) {
  .city-dock { padding-inline: 3px; }
  .dock-inner { gap: 0; }
  .dock-entry { min-height: 64px; padding: 5px 1px 6px; }
  .dock-icon { width: 25px; height: 25px; }
  .dock-label { font-size: 11px; }
  .dock-entry small { display: none; }
  .dock-count { top: -3px; right: -5px; min-width: 16px; height: 16px; font-size: 9px; }
}
@media (max-height: 600px) and (min-width: 641px) { .dock-entry { min-height: 64px; } }
@media (prefers-reduced-motion: reduce) { .dock-icon, .dock-entry { transition: none; } }
</style>
