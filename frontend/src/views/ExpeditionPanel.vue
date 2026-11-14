<script setup lang="ts">
import { computed } from 'vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { type DisplayCatalog } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

defineEmits<{ edit: [] }>()

const store = useGameStore()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const mode = computed(() => catalog.value?.modes?.expedition)
const party = computed(() => store.party.map(id => store.disciples.find(d => d.id === id)).filter(d => !!d))
const onDuty = computed(() => new Set(store.state?.duty_slots?.map(slot => slot.disciple_id) ?? []))
const conflicts = computed(() => party.value.filter(d => d.busy || onDuty.value.has(d.id)))
const cost = computed(() => mode.value?.stamina_cost ?? 2)
const canStart = computed(() => !!mode.value && !store.state?.active_run && party.value.length > 0 && !conflicts.value.length
  && (store.resources?.stamina ?? 0) >= cost.value && !store.busy)
const reason = computed(() => !mode.value
  ? '远行暂不可用，请刷新后查看。'
  : store.state?.active_run
    ? '当前出征尚未结算，请先完成这段行程。'
  : !party.value.length
    ? '请先安排至少一位出征弟子。'
    : conflicts.value.length
      ? '队伍中有值守或出征中的弟子，请先调整。'
      : (store.resources?.stamina ?? 0) < cost.value
        ? '行动力不足，先收取挂机收益再来。'
        : '')
</script>

<template>
  <div class="expedition-layout">
    <div class="expedition-visual">
      <GameIcon name="ship" class="ship-mark" />
      <span class="eyebrow">JOURNEY BEYOND THE MOUNTAIN</span>
      <h3>远行码头</h3>
      <p>顺流出山，寻材问道。</p>
      <span class="badge badge-gold">最高记录 {{ store.state?.expedition_floor ?? 0 }} / {{ mode?.node_count ?? '—' }} 段</span>
    </div>
    <div class="expedition-content">
      <div class="section-heading">
        <div><span class="eyebrow">EXPEDITION DEPARTURE</span><h3>整备远行队伍</h3></div>
        <button class="btn btn-small" @click="$emit('edit')">调整阵容</button>
      </div>
      <PartyStrip compact reorder @edit="$emit('edit')" />
      <p class="muted formation-rule">远征沿用自动回合战斗；队伍顺序决定同身法弟子的出手及目标优先次序。</p>
      <div class="expedition-facts">
        <div><span>行动力消耗</span><strong>{{ number(cost, 1) }} <small>/ 持有 {{ number(store.resources?.stamina, 1) }}</small></strong></div>
        <div><span>远行段数</span><strong>{{ mode?.node_count ?? '—' }} <small>段</small></strong></div>
      </div>
      <div class="expedition-notes">
        <h4>此行规则</h4>
        <p>每段从已知的真实遭遇中选择一条路线，最后一段迎战远行镇守。</p>
        <p>远行更偏向材料收集；战利品在结算前暂存，途中关闭页面可继续。</p>
        <p>落败仍按到达段数带回部分收益，队伍中的弟子可能获得伤势。</p>
      </div>
      <p v-if="party.some(d => d.injury_stacks)" class="notice-box">队伍中有带伤弟子，出征时攻击会受伤势影响。</p>
      <p v-if="reason" class="notice-box">{{ reason }}</p>
      <button class="btn btn-primary start-button" :disabled="!canStart" @click="store.startRun(store.party, 'expedition')"><GameIcon name="ship" />{{ store.busy ? '正在处理…' : '启程远行' }}</button>
    </div>
  </div>
</template>

<style scoped>
.expedition-layout{display:grid;grid-template-columns:270px minmax(0,1fr);gap:32px}.expedition-visual{text-align:center;background:linear-gradient(145deg,#d8e3d1,#f0ead7 72%);padding:35px 20px 30px;border:1px solid #c6c7a7}.ship-mark{width:120px;height:120px;margin:18px auto;color:#557b69;stroke-width:1;filter:drop-shadow(4px 6px 0 #48624b22)}.expedition-visual .eyebrow{display:block;font-size:8px;margin-top:8px}.expedition-visual h3{font-size:26px;margin:8px 0}.expedition-visual p{font-size:12px;color:var(--muted);margin-bottom:14px}.expedition-content .section-heading{margin-top:5px}.expedition-facts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}.expedition-facts>div{padding:14px;background:#e9e5d3}.expedition-facts span{display:block;font-size:11px;color:var(--muted)}.expedition-facts strong{font-size:24px;color:var(--jade)}.expedition-facts small{font-size:11px;color:var(--muted);font-weight:400}.expedition-notes{padding:15px 17px;background:#f5efdd;border:1px solid #d3c6a3}.expedition-notes h4{font-size:14px;margin:0 0 9px}.expedition-notes p{font-size:11px;line-height:1.7;color:var(--muted);margin:5px 0}.start-button{width:100%;margin-top:18px}.start-button .game-icon{width:19px;height:19px;margin-right:6px;vertical-align:-4px}@media(max-width:740px){.expedition-layout{grid-template-columns:1fr;gap:20px}.expedition-visual{padding:14px 20px 18px}.ship-mark{width:70px;height:70px;margin:2px auto}.expedition-visual h3{font-size:22px;margin:5px 0}.expedition-content .section-heading{margin-top:0}.expedition-facts{margin:18px 0}}
</style>
