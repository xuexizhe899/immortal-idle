<script setup lang="ts">
import { computed } from 'vue'
import GameIcon from '../components/GameIcon.vue'
import PartyStrip from '../components/PartyStrip.vue'
import { effectText,number,type DisplayCatalog } from '../components/gameDisplay'
import { useGameStore } from '../stores/game'
defineEmits<{edit:[]}>()
const store=useGameStore()
const catalog=computed(()=>store.catalog as DisplayCatalog|null)
const mode=computed(()=>catalog.value?.mode)
const party=computed(()=>store.disciples.filter(d=>store.party.includes(d.id)))
const onDuty=computed(()=>new Set(store.state?.duty_slots?.map(s=>s.disciple_id)??[]))
const conflicts=computed(()=>party.value.filter(d=>d.busy||onDuty.value.has(d.id)))
const cost=computed(()=>mode.value?.stamina_cost??1)
const canStart=computed(()=>party.value.length>0&&!conflicts.value.length&&(store.resources?.stamina??0)>=cost.value&&!store.busy)
const reason=computed(()=>!party.value.length?'请先安排至少一位出征弟子':conflicts.value.length?'队伍中有值守或出征中的弟子，请先调整':(store.resources?.stamina??0)<cost.value?'行动力不足，稍后收取挂机收益再来':'')
const activeBonds=computed(()=>Object.entries(catalog.value?.bonds??{}).filter(([,b])=>b.members.filter(id=>party.value.some(d=>d.template_id===id)).length>=(b.requires??b.members.length)))
</script>
<template><div class="prepare-layout"><div class="prepare-visual"><img src="/assets/buildings/sprite_tower.png" alt="问道塔" class="pixel-art" /><span class="eyebrow">TRIAL OF THE IMMORTALS</span><h3>登临问道塔</h3><p>一层一境，相携而行。</p><span class="badge badge-gold">最高记录 {{ store.state?.tower_floor??0 }} 层</span></div><div class="prepare-content"><div class="section-heading"><h3>此次出征</h3><button class="btn btn-small" @click="$emit('edit')">调整阵容</button></div><PartyStrip compact @edit="$emit('edit')" /><div class="prepare-facts"><div><span>行动力消耗</span><strong>{{ number(cost) }} <small>/ 持有 {{ number(store.resources?.stamina,1) }}</small></strong></div><div><span>问道塔层数</span><strong>{{ mode?.node_count??'—' }} <small>层</small></strong></div></div><div class="bonds"><h4>阵容羁绊</h4><div v-for="[id,bond] in activeBonds" :key="id" class="bond-line"><span class="badge">{{ bond.name }}</span><span v-for="(e,i) in bond.effects" :key="i" class="muted">{{ effectText(e) }}</span></div><p v-if="!activeBonds.length" class="muted">暂未组成羁绊，可在弟子详情中查看同道组合。</p></div><div v-if="party.some(d=>d.injury_stacks)" class="notice-box">队伍中有带伤弟子，出征时攻击会受伤势影响。</div><p class="prepare-rule muted">出发消耗行动力。途中关闭页面可继续上次出征；落败仍有部分收益，弟子可能受伤。</p><p v-if="reason" class="error-box">{{ reason }}</p><button class="btn btn-primary start-button" :disabled="!canStart" @click="store.startRun(store.party)"><GameIcon name="tower" />踏上问道之路</button></div></div></template>
<style scoped>
.prepare-layout{display:grid;grid-template-columns:300px minmax(0,1fr);gap:35px}.prepare-visual{text-align:center;background:radial-gradient(ellipse,#d5e0c6,#ece9d8 70%);padding:10px 20px 30px;border:1px solid #d1c8ac}.prepare-visual>img{height:290px;object-fit:contain;filter:drop-shadow(3px 8px 3px #234e4020)}.prepare-visual .eyebrow{font-size:8px;margin-top:10px}.prepare-visual h3{font-size:26px;margin:8px 0}.prepare-visual p{font-size:12px;color:var(--muted);margin-bottom:14px}.prepare-content .section-heading{margin-top:5px}.prepare-facts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}.prepare-facts>div{padding:14px;background:#e9e5d3}.prepare-facts span{display:block;font-size:11px;color:var(--muted)}.prepare-facts strong{font-size:25px;color:var(--jade)}.prepare-facts small{font-size:11px;color:var(--muted);font-weight:400}.bonds h4{font-size:14px;margin-bottom:10px}.bond-line{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}.prepare-rule{margin:22px 0 16px}.start-button{width:100%;margin-top:8px}.prepare-content>.error-box{font-size:12px}
@media(max-width:740px){.prepare-layout{grid-template-columns:1fr;gap:20px}.prepare-visual{display:none}.prepare-facts{margin:18px 0}.prepare-content .section-heading{margin-top:0}}
</style>
