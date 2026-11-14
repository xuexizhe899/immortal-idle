<script setup lang="ts">
import { computed, ref } from 'vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import PartyHealing from '../components/game/PartyHealing.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { TOWER_SPRITE_IMAGE } from '../presentation/assetPaths'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

defineEmits<{ edit: [] }>()
const store = useGameStore()
const tier = ref(1)
const mode = computed(() => store.catalog?.mode)
const party = computed(() => store.party.map(id => store.disciples.find(d => d.id === id)).filter(d => !!d))
const cost = computed(() => mode.value?.stamina_cost ?? 1)
const currentBest = computed(() => tier.value === 1
  ? Math.max(store.state?.tower_floor ?? 0, store.state?.tower_tiers['1'] ?? 0)
  : store.state?.tower_tiers[String(tier.value)] ?? 0)
const reason = computed(() => {
  if (!party.value.length) return '请先安排至少一位出征弟子'
  if (party.value.some(d => d.busy)) return '队伍中有正在出征的弟子'
  if (tier.value > (store.state?.facility_levels.tower ?? 1)) return '先在宗门主殿升级问道塔，再挑战这一阶'
  const previous = tier.value === 2
    ? Math.max(store.state?.tower_floor ?? 0, store.state?.tower_tiers['1'] ?? 0)
    : store.state?.tower_tiers[String(tier.value - 1)] ?? 0
  if (tier.value > 1 && previous < 20) return '需要先通关前一阶问道塔'
  return (store.resources?.stamina ?? 0) < cost.value ? '行动力不足，稍后收取挂机收益再来' : ''
})
const activeBonds = computed(() => Object.entries(store.catalog?.bonds ?? {}).filter(([, bond]) =>
  bond.modifiers.length > 0
  && bond.members.filter(id => party.value.some(d => d.template_id === id)).length >= bond.requires,
))
</script>
<template>
  <div class="prepare-layout">
    <div class="prepare-visual">
      <img :src="TOWER_SPRITE_IMAGE" alt="问道塔" class="pixel-art" />
      <span class="eyebrow">层境问道 · 同行试炼</span>
      <h3>登临问道塔</h3>
      <p>一层一境，相携而行。</p>
      <span class="badge badge-gold">第 {{ tier }} 阶 · 最高 {{ currentBest }} 层</span>
    </div>
    <div class="prepare-content">
      <div class="section-heading">
        <h3>此次出征</h3>
        <button class="btn btn-small" @click="$emit('edit')">调整阵容</button>
      </div>
      <label class="tier-field">
        挑战塔阶
        <select v-model.number="tier">
          <option v-for="i in 3" :key="i" :value="i">
            第
            {{ i }}
            阶
            {{ i > (store.state?.facility_levels.tower ?? 1) ? ' · 需升级设施' : '' }}
          </option>
        </select>
      </label>
      <PartyStrip compact reorder @edit="$emit('edit')" />
      <p class="muted formation-rule">可直接选择值守或驻守弟子，出发自动离岗，结算后自动回岗。队列顺序影响同身法时的行动与目标优先次序。</p>
      <PartyHealing :party="store.party" />
      <div class="prepare-facts">
        <div>
          <span>行动力消耗</span>
          <strong>
            {{ number(cost) }}
            <small>/ 持有 {{ number(store.resources?.stamina,1) }}</small>
          </strong>
        </div>
        <div>
          <span>本阶挑战</span>
          <strong>
            {{ mode?.node_count ?? 20 }}
            <small>层</small>
          </strong>
        </div>
      </div>
      <div class="bonds">
        <h4>战斗羁绊</h4>
        <div v-for="[id,bond] in activeBonds" :key="id" class="bond-line">
          <span class="badge">{{ bond.name }}</span>
          <span class="muted">{{ bond.description }}</span>
        </div>
        <p v-if="!activeBonds.length" class="muted">暂未组成羁绊，可在弟子堂查看同道组合。</p>
      </div>
      <p class="prepare-rule muted">途中关闭页面可继续上次出征；落败仍有部分收益，弟子可能受伤。</p>
      <p v-if="reason" class="error-box">{{ reason }}</p>
      <button
        class="btn btn-primary start-button"
        :disabled="!!reason || store.busy"
        @click="store.startRun(store.party,'tower',{tower_tier:tier})"
      >
        <GameIcon name="tower" />
        踏上问道之路
      </button>
    </div>
  </div>
</template>
<style scoped>
.prepare-layout{display:grid;grid-template-columns:300px minmax(0,1fr);gap:35px}.prepare-visual{text-align:center;background:radial-gradient(ellipse,#d5e0c6,#ece9d8 70%);padding:10px 20px 30px;border:1px solid #d1c8ac}.prepare-visual>img{height:290px;object-fit:contain;filter:drop-shadow(3px 8px 3px #234e4020)}.prepare-visual .eyebrow{font-size:8px;margin-top:10px}.prepare-visual h3{font-size:26px;margin:8px 0}.prepare-visual p{font-size:12px;color:var(--muted);margin-bottom:14px}.prepare-content .section-heading{margin-top:5px}.prepare-facts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}.prepare-facts>div{padding:14px;background:#e9e5d3}.prepare-facts span{display:block;font-size:11px;color:var(--muted)}.prepare-facts strong{font-size:25px;color:var(--jade)}.prepare-facts small{font-size:11px;color:var(--muted);font-weight:400}.bonds h4{font-size:14px;margin-bottom:10px}.bond-line{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}.prepare-rule{margin:22px 0 16px}.start-button{width:100%;margin-top:8px}.prepare-content>.error-box{font-size:12px}
@media(max-width:740px){.prepare-layout{grid-template-columns:1fr;gap:20px}.prepare-visual{display:none}.prepare-facts{margin:18px 0}.prepare-content .section-heading{margin-top:0}}
</style>

<style scoped>.tier-field{display:flex;align-items:center;justify-content:space-between;gap:16px;font-size:12px;margin:15px 0}.tier-field select{min-width:160px}</style>
