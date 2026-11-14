<script setup lang="ts">
import CityNavIcon from './CityNavIcon.vue'
defineProps<{ towerLabel: string; towerHint: string; expeditionLabel: string; expeditionHint: string; discipleCount: number; dutyCount: number; active: string | null }>()
defineEmits<{ open: [panel: string] }>()
const entries = [{ id: 'sect', label: '宗门', hint: '设施 · 存档' }, { id: 'codex', label: '弟子', hint: '修炼 · 招贤' }, { id: 'duty', label: '值守', hint: '同道守山' }, { id: 'alchemy', label: '炼丹', hint: '丹火养元' }, { id: 'forge', label: '炼器', hint: '百炼成器' }, { id: 'expedition', label: '远行', hint: '征讨 · 驻守' }, { id: 'tower', label: '问道', hint: '登塔试炼' }]
</script>
<template>
  <nav class="city-dock" aria-label="宗门功能">
    <div class="dock-inner">
      <button v-for="entry in entries" :key="entry.id" :class="['dock-entry', { 'dock-tower': entry.id === 'tower', 'dock-expedition': entry.id === 'expedition', selected: active === entry.id }]" :aria-label="entry.id === 'tower' ? `${towerLabel}，${towerHint}` : entry.id === 'expedition' ? `${expeditionLabel}，${expeditionHint}` : entry.label" @click="$emit('open', entry.id)">
        <span class="dock-icon"><CityNavIcon :name="entry.id" /><span v-if="entry.id === 'codex' && discipleCount" class="dock-count">{{ discipleCount }}</span><i v-if="(entry.id === 'tower' && towerLabel !== '问道') || (entry.id === 'expedition' && expeditionLabel !== '远行')" class="run-dot"></i></span>
        <span class="dock-label">{{ entry.id === 'tower' ? towerLabel : entry.id === 'expedition' ? expeditionLabel : entry.label }}</span>
        <small>{{ entry.id === 'tower' ? towerHint : entry.id === 'expedition' ? expeditionHint : entry.id === 'duty' ? `${dutyCount} 位值守` : entry.hint }}</small>
      </button>
    </div>
  </nav>
</template>
<style scoped>
.city-dock{position:relative;z-index:10;flex:none;padding:0 24px env(safe-area-inset-bottom);background:linear-gradient(#f9f3e2,#e8dfc5);border-top:2px solid #ad9866;box-shadow:0 -6px 24px #27483b22,inset 0 3px #fffaec}.city-dock::before{content:'';position:absolute;inset:6px 12px auto;height:1px;background:#cdbb91;pointer-events:none}.dock-inner{max-width:1020px;margin:auto;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}.dock-entry{position:relative;min-height:104px;padding:6px 4px 8px;border:0;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#355447;transition:background .15s}.dock-entry:hover,.dock-entry.selected{background:#d5dfc466}.dock-icon{position:relative;display:block;width:42px;height:42px}.dock-icon svg{width:100%;height:100%;filter:drop-shadow(0 2px #a2967133)}.dock-label{font:600 17px/1.5 'SimSun',serif;letter-spacing:.14em;padding-left:.14em}.dock-entry small{font-size:10px;color:#7a8069;white-space:nowrap}.dock-count{position:absolute;top:0;right:-8px;min-width:17px;height:17px;padding:0 3px;background:#f8f0d9;border:1px solid #b4a477;font-size:10px;line-height:15px;color:#4a654b}.dock-tower{border-inline:1px solid #c8b47e;background:linear-gradient(#e6ddba99,#d6c89755);box-shadow:inset 0 3px #bd984e}.dock-tower .dock-icon{width:48px;height:48px;margin-top:-7px}.dock-tower .dock-label{color:#735621}.dock-expedition .dock-icon{color:#557b69}.run-dot{position:absolute;right:0;top:5px;width:7px;height:7px;background:#aa5837;box-shadow:0 0 0 2px #f6edcf}
@media(max-width:640px){.city-dock{padding-inline:5px}.dock-inner{gap:0}.dock-entry{min-height:90px;padding:6px 1px}.dock-icon{width:34px;height:34px}.dock-label{font-size:14px;letter-spacing:.03em}.dock-entry small{font-size:8px}.dock-tower .dock-icon{width:40px;height:40px;margin-top:-6px}.dock-tower .dock-label{font-size:13px;letter-spacing:0}.dock-count{right:-4px;min-width:15px;height:15px;line-height:13px;font-size:9px}}
</style>
