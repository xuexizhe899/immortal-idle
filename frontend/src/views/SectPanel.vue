<script setup lang="ts">
import { computed,ref } from 'vue'
import { useGameStore } from '../stores/game'
import { number,statNames } from '../components/gameDisplay'
import GameIcon from '../components/GameIcon.vue'
import SaveSlotsPanel from './SaveSlotsPanel.vue'
const store=useGameStore();const tab=ref('overview')
const settleGains=computed(()=>store.lastSettle ? {cultivation:store.lastSettle.gained.cultivation,spirit_stone:store.lastSettle.gained.spirit_stone,stamina:store.lastSettle.gained.stamina,...store.lastSettle.gained.materials} : {})
const chronicles=computed(()=>[
  `问道塔已至 ${store.state?.tower_floor??0} 层，新的修行之路仍在前方。`,
  `门下共有 ${store.disciples.length} 位弟子，${store.state?.duty_slots?.length??0} 位正在值守。`,
  store.disciples.some(d=>d.injury_stacks) ? `${store.disciples.filter(d=>d.injury_stacks).length} 位弟子有伤在身，可前往炼丹房疗伤。` : '门下弟子状态良好，随时可整装出发。',
])
</script>
<template><div class="tabs" role="tablist" aria-label="宗门事务"><button :class="{active:tab==='overview'}" role="tab" :aria-selected="tab==='overview'" @click="tab='overview'">宗门总览</button><button :class="{active:tab==='saves'}" role="tab" :aria-selected="tab==='saves'" @click="tab='saves'">存档管理</button></div><SaveSlotsPanel v-if="tab==='saves'" /><template v-else><div class="sect-intro"><span class="sect-seal">仙</span><div><span class="eyebrow">云岫仙宗</span><h3>山中无甲子，修行有所得。</h3><p class="muted">门下 {{ store.disciples.length }} 位弟子 · 值守 {{ store.state?.duty_slots?.length??0 }} / 6 · 问道塔 {{ store.state?.tower_floor??0 }} 层</p></div></div><div class="stat-grid"><div v-for="key in ['cultivation','spirit_stone','stamina','reputation'] as const" :key="key" class="stat-cell"><span>{{ statNames[key] }}</span><strong>{{ number(store.resources?.[key],1) }}</strong></div></div><div class="idle-section"><div><h3>收取挂机收益</h3><p class="muted">离开后宗门仍在修行，最多结算 12 小时收益。</p></div><button class="btn btn-primary" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" />收取收益</button></div><div v-if="store.lastSettle" class="settle-result notice-box"><span class="eyebrow">此次修行所得</span><p>已结算 {{ number(store.lastSettle.elapsed_hours,2) }} 小时</p><div class="chips"><span v-for="(n,key) in settleGains" :key="key" class="badge">{{ statNames[key]??key }} +{{ number(n,2) }}</span></div><p v-if="store.lastSettle.dropped_hours>0" class="muted">超出 12 小时的 {{ number(store.lastSettle.dropped_hours,1) }} 小时不计入收益。</p></div><div class="sect-log"><div class="section-heading"><h3>宗门现况</h3><span class="muted">当前修行进度</span></div><p v-for="(log,i) in chronicles" :key="i">{{ log }}</p><p v-if="!store.state?.logs?.length" class="muted">新宗初立，来日方长。</p></div></template></template>
<style scoped>
.sect-intro{display:flex;align-items:center;gap:22px;margin:12px 0 28px}.sect-seal{width:72px;height:82px;display:grid;place-items:center;border:1px solid #a59f7c;box-shadow:inset 0 0 0 5px var(--surface),inset 0 0 0 6px #a59f7c;color:var(--jade);font:43px 'SimSun',serif}.sect-intro h3{font-size:23px;margin:6px 0}.sect-intro p{margin:0}.idle-section{display:flex;justify-content:space-between;gap:20px;align-items:center;margin:26px 0 18px;padding:22px 0;border-block:1px solid #d5c9ad}.idle-section h3{margin:0 0 7px}.idle-section p{margin:0}.settle-result>.eyebrow{font-size:8px}.settle-result p{margin:5px 0 10px}.settle-result .muted{margin:12px 0 0}.sect-log{margin-top:28px}.sect-log>p{font-size:11px;padding:8px 0;border-bottom:1px solid #ded5bf;margin:0;color:var(--muted)}
@media(max-width:640px){.sect-intro{gap:14px;margin-bottom:20px}.sect-seal{width:52px;height:65px;flex:none;font-size:32px}.sect-intro h3{font-size:18px}.sect-intro .eyebrow{font-size:8px}.idle-section{flex-direction:column;align-items:flex-start;gap:14px}.idle-section>.btn{width:100%}}
</style>
