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
const currentBest = computed(() => tier.value === 1 && (store.state?.world.current_region ?? 1) === 1
  ? Math.max(store.state?.tower_floor ?? 0, store.state?.tower_tiers['1'] ?? 0)
  : store.state?.tower_tiers[String(tier.value)] ?? 0)
const reason = computed(() => {
  if (!party.value.length) return '请先安排至少一位出征弟子'
  if (party.value.some(d => d.busy)) return '队伍中有正在出征的弟子'
  if (tier.value > (store.state?.facility_levels.tower ?? 1)) return '先在宗门主殿升级问道塔，再挑战这一阶'
  const previous = tier.value === 2 && (store.state?.world.current_region ?? 1) === 1
    ? Math.max(store.state?.tower_floor ?? 0, store.state?.tower_tiers['1'] ?? 0)
    : store.state?.tower_tiers[String(tier.value - 1)] ?? 0
  if (tier.value > 1 && previous < 20) return '需要先通关前一阶问道塔'
  return (store.resources?.stamina ?? 0) < cost.value ? '行动力不足，稍后同步挂机收益再来' : ''
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
      <div class="tower-record"><span>第 {{ tier }} 阶修行记录</span><strong>{{ currentBest }} <small>/ {{ mode?.node_count ?? 20 }} 层</small></strong><div class="tower-record-track" aria-hidden="true"><i :style="{width:`${Math.min(100,currentBest/(mode?.node_count??20)*100)}%`}"></i></div></div>
    </div>
    <div class="prepare-content">
      <div class="section-heading">
        <h3>此次出征</h3>
        <button class="btn btn-small" @click="$emit('edit')">调整阵容</button>
      </div>
      <label class="tier-field">
        <span>挑战塔阶 <small class="tier-best">本阶最高 {{ currentBest }} 层</small></span>
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
      <p class="prepare-rule muted">途中关闭页面可继续上次出征；落败仍可带回途中已获得的装备，资源按规则折算，弟子可能受伤。</p>
      <p v-if="reason" class="error-box">{{ reason }}</p>
      <button
        class="btn btn-primary start-button"
        :disabled="!!reason || store.busy"
        @click="store.startRun(store.party,'tower',{tower_tier:tier})"
      >
        <GameIcon name="tower" />
        踏上问道之路
      </button>
      <details class="bonds"><summary>战斗羁绊 · {{ activeBonds.length }} 组</summary>
        <div v-for="[id,bond] in activeBonds" :key="id" class="bond-line">
          <span class="badge">{{ bond.name }}</span>
          <span class="muted">{{ bond.description }}</span>
        </div>
        <p v-if="!activeBonds.length" class="muted">暂未组成羁绊，可在弟子堂查看同道组合。</p>
      </details>
    </div>
  </div>
</template>
<style scoped>
.prepare-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:28px}.prepare-visual{position:relative;text-align:center;background:repeating-linear-gradient(0deg,transparent 0 27px,#8c68440a 27px 28px),#e4e9d4;padding:8px 20px 20px;border:1px solid #a8b18b;box-shadow:inset 0 4px #8c6844,inset 0 0 0 6px #f6f1df}.prepare-visual>img{position:relative;z-index:1;max-width:100%;height:250px;object-fit:contain;filter:drop-shadow(3px 8px 0 #234e401a)}.prepare-visual .eyebrow{font-size:8px;margin-top:10px}.prepare-visual h3{font-size:26px;margin:8px 0}.prepare-visual p{font-size:12px;color:var(--muted);margin-bottom:14px}.prepare-content .section-heading{margin-top:5px}.prepare-facts{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:18px 0;border-block:1px solid #c4b68f;background:#f0ebd7}.prepare-facts>div{padding:12px 16px}.prepare-facts>div+div{border-left:1px solid #c4b68f}.prepare-facts span{display:block;font-size:11px;color:var(--muted)}.prepare-facts strong{font-size:25px;color:var(--jade)}.prepare-facts small{font-size:11px;color:var(--muted);font-weight:400}.bonds{margin-top:18px}.bonds summary{cursor:pointer;min-height:44px;padding:10px 0;font-size:14px;color:var(--jade)}.bonds summary:focus-visible{outline:2px solid var(--jade);outline-offset:2px}.bond-line{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}.prepare-rule{margin:16px 0 12px;font-size:12px;line-height:1.8}.start-button{width:100%;min-height:48px;margin-top:8px;box-shadow:inset 0 -3px #213f3655,0 2px 0 #8c684433}.prepare-content>.error-box{font-size:12px}
@media(max-width:740px){.prepare-layout{grid-template-columns:1fr;gap:20px}.prepare-visual{display:none}.prepare-facts{margin:18px 0}.prepare-content .section-heading{margin-top:0}}
</style>

<style scoped>.tier-field{display:flex;align-items:center;justify-content:space-between;gap:16px;font-size:12px;margin:15px 0}.tier-field select{min-width:160px}
.prepare-visual::before{content:'';position:absolute;width:178px;height:178px;border-radius:50%;top:52px;left:50%;transform:translateX(-50%);border:1px solid #acba96;box-shadow:0 0 0 9px #cdd8bb55,0 0 0 10px #afbd9833}.tower-record{margin:16px auto 0;max-width:185px;padding-top:12px;border-top:1px solid #b2b995;color:#6d7e60;font-size:11px}.tower-record>span{display:block}.tower-record>strong{display:block;font:29px SimSun,serif;color:#326c55;margin:6px 0 10px}.tower-record small{font:11px system-ui;color:#6d7e60}.tower-record-track{height:4px;background:#becbaa}.tower-record-track>i{display:block;height:100%;background:#326c55;border-right:3px solid #b38a46}.formation-rule{font-size:11px;line-height:1.9;margin:10px 0;color:#6a795f}.prepare-content .section-heading h3{color:#213f36}.bonds{border-top:1px solid #c8bea1}.tier-best{display:block;color:#768267;font-size:10px;margin-top:3px}.tier-field select:focus-visible{outline:2px solid #b38a46;outline-offset:2px}
@media(max-width:740px){.prepare-content{min-width:0}.prepare-layout{gap:0}.prepare-facts>div{padding:12px}.formation-rule{font-size:12px}.tier-field select{min-height:44px}.start-button{min-height:48px}}

</style>
