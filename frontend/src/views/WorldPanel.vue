<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { WorldNode } from '../api/client'
import PartyStrip from '../components/game/PartyStrip.vue'
import PartyHealing from '../components/game/PartyHealing.vue'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import ExpeditionPanel from './ExpeditionPanel.vue'

defineEmits<{ edit: [] }>()
const store = useGameStore()
const selectedId = ref('')
const showingSect = ref(false)
const towerTier = ref(1)
const region = computed(() => store.worldMap?.regions.find(item => item.selected))
const selected = computed(() => region.value?.nodes.find(item => item.id === selectedId.value))
const targetSect = computed(() => {
  if (!store.targetSectId) return null
  for (const item of store.worldMap?.regions ?? []) {
    const node = item.nodes.find(node => node.kind === 'sect' && node.sect_id === store.targetSectId)
    if (node) return { region: item, node }
  }
  return null
})
const targetElsewhere = computed(() => targetSect.value && targetSect.value.region.id !== region.value?.id ? targetSect.value : null)
let locatedTargetId = ''
const nodeNames = { sect: '宗门', dungeon: '秘境', gate: '守关', invasion: '关键入侵', raid: '普通迎击', tower: '问道塔' }
const nodeMarks = { sect: '宗', dungeon: '境', gate: '关', invasion: '敌', raid: '守', tower: '塔' }
const slots: Record<string, string> = { weapon: '武器', armor: '盔甲', boots: '靴子', ring: '戒指' }
const startReason = computed(() => {
  if (!selected.value) return '请在地图中选择一个据点'
  if (store.state?.active_run) return '请先完成并结算当前出征'
  if (selected.value.locked) return selected.value.reason
  if (!store.party.length) return '请先选择出征弟子'
  if ((store.resources?.stamina ?? 0) < selected.value.stamina_cost) return '行动力不足，可收取挂机收益，或迎击、演练'
  return ''
})
const practiceReason = computed(() => {
  if (store.state?.active_run) return '请先结算当前出征'
  if (!store.party.length) return '请先选择出征弟子'
  if (selected.value?.locked && selected.value.kind !== 'raid') return selected.value.reason
  return ''
})
const canPractice = computed(() => selected.value && ['gate', 'invasion', 'raid'].includes(selected.value.kind))
watch([() => store.slotId, () => store.revision], () => { void store.loadWorld() }, { immediate: true })
watch([region, () => store.targetSectId], ([value, targetId], [previous]) => {
  const changedRegion = value?.id !== previous?.id
  if (!targetId) locatedTargetId = ''
  const target = value?.nodes.find(node => node.kind === 'sect' && node.sect_id === targetId)
  if (changedRegion || (targetId && !target)) showingSect.value = false
  if (target && (locatedTargetId !== targetId || changedRegion)) {
    selectedId.value = target.id
    showingSect.value = !target.locked
    locatedTargetId = targetId
    return
  }
  if (!value?.nodes.some(node => node.id === selectedId.value)) {
    selectedId.value = value?.nodes.find(node => node.kind === 'dungeon' && !node.locked)?.id ?? value?.nodes[0]?.id ?? ''
  }
}, { immediate: true })
function choose(node: WorldNode) {
  selectedId.value = node.id
  showingSect.value = false
  store.targetSectId = ''
}
function openSect() {
  if (!selected.value?.sect_id) return
  store.targetSectId = selected.value.sect_id
  showingSect.value = true
}
</script>

<template>
  <section class="world-atlas" aria-label="山河地图">
    <header class="atlas-heading">
      <div><h3>山河行记</h3><p>寻器养成，攻宗守山；以一枚升仙令，叩开下一重天地。</p></div>
      <button class="btn btn-small" :disabled="store.busy || store.worldLoading" @click="store.settle()">收取收益与敌情</button>
    </header>
    <nav class="region-switch" aria-label="地区图层">
      <button v-for="item in store.worldMap?.regions" :key="item.id" :class="{ active: item.selected }"
        :disabled="store.busy || !item.unlocked || !!store.state?.active_run" :aria-current="item.selected ? 'location' : undefined"
        :title="item.unlocked ? '免费往返，保留原有成长与驻守' : '击退前一地区最终入侵后飞升解锁'" @click="store.travelRegion(item.id)">
        {{ item.name }}<small>{{ item.unlocked ? item.selected ? '当前所在' : '已开放' : '待飞升' }}</small>
      </button>
    </nav>
    <div v-if="targetElsewhere" class="notice-box" role="status">
      <p>目标宗门「{{ targetElsewhere.node.name }}」位于{{ targetElsewhere.region.name }}。</p>
      <p v-if="targetElsewhere.node.locked">{{ targetElsewhere.node.reason }}</p>
      <button v-else class="btn btn-small" :disabled="store.busy || !!store.state?.active_run"
        @click="store.travelRegion(targetElsewhere.region.id, targetElsewhere.node.sect_id)">切换地区并查看目标宗门</button>
    </div>
    <p v-if="store.worldLoading && !store.worldMap" role="status" class="notice-box">正在展开山河图……</p>
    <div v-else-if="!region" class="empty-state"><p>暂未取得地图，请恢复连接后重试。</p><button class="btn" @click="store.loadWorld()">重试载入地图</button></div>
    <template v-else>
      <div class="region-intro"><div><h4>{{ region.name }}</h4><p>{{ region.subtitle }}</p></div><span>已开放 {{ region.areas.filter(area => area.unlocked).length }} / {{ region.areas.length }} 片区</span></div>
      <div class="atlas-layout">
        <div class="map-scroll">
          <div class="map-board" :class="region.palette">
            <svg viewBox="0 0 1000 650" preserveAspectRatio="none" aria-hidden="true">
              <defs><pattern id="atlas-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#70876b" stroke-opacity=".09"/></pattern></defs>
              <rect width="1000" height="650" fill="url(#atlas-grid)"/>
              <path d="M40 590 90 540 150 560 230 490 280 530 350 450 410 475 480 390 550 420 630 340 690 375 770 275 850 310 940 215" class="mountain"/>
              <path d="M-20 270Q130 165 235 270T475 290T720 220T1030 180" class="river"/>
              <path d="M180 125V525M500 125V525M820 125V525M180 395H820M90 610 180 525M820 525 910 610" class="roads"/>
            </svg>
            <div v-for="area in region.areas" :key="area.id" class="area-label" :class="{ sealed: !area.unlocked }" :style="{ left: `${18 + (area.id - 1) * 32}%` }">
              <strong>{{ area.name }}</strong><small>{{ area.unlocked ? '片区内自由选择' : '击败前关后开放' }}</small>
            </div>
            <button v-for="node in region.nodes" :key="node.id" class="map-node" :class="[node.kind, { selected: selectedId === node.id, locked: node.locked, cleared: node.cleared }]"
              :style="{ left: `${node.x}%`, top: `${node.y}%` }" :aria-pressed="selectedId === node.id"
              :aria-label="`${node.name}，${node.locked ? node.reason : node.cleared ? '已完成，可查看' : nodeNames[node.kind]}`" :title="node.name" @click="choose(node)">
              <span class="node-mark">{{ node.cleared ? '成' : nodeMarks[node.kind] }}</span><span class="node-name">{{ node.name }}</span>
            </button>
          </div>
          <p class="map-legend">宗门产材，秘境寻器；守关开启下一片区，关键入侵推进飞升。</p>
        </div>
        <aside v-if="selected" class="node-detail" aria-live="polite">
          <span class="badge">{{ nodeNames[selected.kind] }}<template v-if="selected.cleared"> · 已完成</template></span>
          <h4>{{ selected.name }}</h4><p>{{ selected.description }}</p>
          <div class="target-facts"><span>行动力 <strong>{{ selected.stamina_cost }}</strong></span><span>敌人强度 <strong>×{{ selected.enemy_scale.toFixed(2) }}</strong></span></div>
          <p v-if="selected.gear_slot" class="notice-box">定向掉落{{ slots[selected.gear_slot] }}，{{ selected.gear_tier }}阶装备；首领必掉一件。</p>
          <p v-else-if="selected.kind === 'dungeon'" class="notice-box">四部位随机掉落，首领必掉一件。失败可带回此前已获得的装备与材料。</p>
          <div v-if="selected.enemy_ids.length" class="enemy-preview"><strong>敌情</strong><span v-for="enemy in selected.enemy_ids" :key="enemy">{{ store.catalog?.enemies[enemy]?.name ?? enemy }}</span></div>
          <div v-if="Object.keys(selected.rewards).length" class="node-rewards"><strong>{{ selected.kind === 'raid' ? '本波胜利奖励' : '首次胜利奖励' }}</strong><span v-for="(amount, key) in selected.rewards" :key="key">{{ resourceName(String(key), store.catalog) }} +{{ number(amount) }}</span><small v-if="selected.cleared && selected.kind !== 'sect'">首胜已领取，重复挑战不再发放。</small></div>
          <p v-if="selected.locked" class="locked-reason">{{ selected.reason }}</p>
          <button v-if="selected.kind === 'sect'" class="btn btn-primary" :disabled="selected.locked || store.busy" @click="openSect">查看征讨与驻守</button>
          <template v-else>
            <PartyStrip compact @edit="$emit('edit')"/>
            <PartyHealing v-if="store.party.length" :party="store.party"/>
            <label v-if="selected.kind === 'tower'" class="tier-select">塔阶<select v-model.number="towerTier"><option v-for="tier in store.state?.facility_levels.tower ?? 1" :key="tier" :value="tier">第{{ tier }}阶</option></select></label>
            <button class="btn btn-primary" :disabled="store.busy || !!startReason" @click="store.startWorld(selected.id, false, towerTier)">{{ selected.kind === 'raid' || selected.kind === 'invasion' ? '正式迎击' : '出发挑战' }} · {{ selected.stamina_cost }} 行动力</button>
            <p v-if="startReason" class="action-reason">{{ startReason }}</p>
            <button v-if="canPractice" class="btn" :disabled="store.busy || !!practiceReason" @click="store.startWorld(selected.id, true)">阵容演练 · 无消耗无奖励</button>
            <small v-if="canPractice">可先演练试阵，再决定是否正式接战。演练不增加伤势、不推进波次，也不获得装备、材料与升仙令。</small>
          </template>
        </aside>
      </div>
      <section v-if="showingSect" class="sect-sheet"><button class="btn btn-small" @click="showingSect = false">收起宗门详情</button><ExpeditionPanel @edit="$emit('edit')"/></section>
      <footer class="atlas-footer">
        <div><h4>守山敌情 {{ store.worldMap?.invasions.pending }} / {{ store.worldMap?.invasions.cap }}</h4><p>每 {{ store.worldMap?.invasions.hours_per_wave }} 小时积攒一次，上限后停止积攒。正式迎击不耗行动力，失败保留本波。</p></div>
        <div><h4>飞升新境</h4><p>升仙令 {{ store.worldMap?.ascension.held ?? 0 }} / 1</p><button class="btn btn-primary" :disabled="store.busy || !store.worldMap?.ascension.can_ascend" @click="store.ascend()">消耗一枚升仙令 · 飞升</button><small>{{ store.worldMap?.ascension.reason || '弟子、装备、强化与旧区驻守全部保留。' }}</small></div>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.world-atlas{color:#354d3d}.atlas-heading,.region-intro{display:flex;align-items:center;justify-content:space-between;gap:16px}.atlas-heading h3{font:26px 'SimSun',serif;margin:0 0 6px}.atlas-heading p,.region-intro p{font-size:12px;color:var(--muted);margin:0;line-height:1.7}.region-switch{display:flex;gap:8px;margin:20px 0 16px;flex-wrap:wrap}.region-switch button{border:1px solid #b7b499;background:#e9e8d6;color:#476049;padding:10px 18px;font:16px 'SimSun',serif}.region-switch button.active{background:#355c47;color:#fff4d6;border-color:#355c47}.region-switch small{display:block;font:10px/1.8 'Microsoft YaHei',sans-serif;opacity:.8}.region-intro{margin-bottom:12px}.region-intro h4{font-size:19px;margin:0 0 4px}.region-intro>span{font-size:11px;color:var(--muted)}.atlas-layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:16px;align-items:start}.map-scroll{min-width:0}.map-board{position:relative;height:510px;background:#e1e4c9;border:1px solid #acb394;box-shadow:inset 0 0 0 5px #f3edda;overflow:hidden}.map-board.azure{background:#dce5dc}.map-board>svg{position:absolute;width:100%;height:100%;inset:0}.mountain{fill:none;stroke:#a1b28c;stroke-width:36;stroke-linejoin:bevel;opacity:.28}.river{fill:none;stroke:#b0cbb8;stroke-width:19;opacity:.65}.roads{fill:none;stroke:#9b906a;stroke-width:2;stroke-dasharray:6 6;opacity:.6}.area-label{position:absolute;top:14px;transform:translateX(-50%);text-align:center;white-space:nowrap}.area-label strong{font:15px 'SimSun',serif}.area-label small{display:block;font-size:9px;margin-top:4px;color:#738263}.area-label.sealed{opacity:.5}.map-node{position:absolute;transform:translate(-50%,-50%);border:0;background:none;display:flex;flex-direction:column;align-items:center;width:85px;padding:3px;color:#365b44;cursor:pointer}.node-mark{display:grid;place-items:center;width:31px;height:31px;background:#faf1d4;border:2px solid #73916b;font:16px 'SimSun',serif;box-shadow:0 2px 0 #6c795933}.node-name{max-width:85px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:9px;background:#f5efd9e8;padding:2px 4px;margin-top:3px}.map-node.dungeon .node-mark{border-radius:50%}.map-node.gate .node-mark,.map-node.invasion .node-mark{border-color:#a77d44;color:#805a2f}.map-node.selected .node-mark{outline:2px solid #345b44;outline-offset:3px;background:#355e47;color:#fff3d0}.map-node.locked{opacity:.52}.map-node.cleared:not(.selected) .node-mark{background:#bdd0a8}.map-node:focus-visible{outline:2px solid #a47732;outline-offset:4px}.map-legend{font-size:11px;color:var(--muted);line-height:1.8;margin:9px 0}.node-detail{border-top:3px solid #9b8051;padding:15px;background:#eee9d7;min-width:0}.node-detail h4{font-size:20px;margin:12px 0}.node-detail p{font-size:12px;line-height:1.9}.target-facts{display:flex;gap:15px;font-size:11px;padding:10px 0;border-block:1px solid #d1c7aa}.target-facts strong{display:block;font-size:17px;margin-top:4px}.enemy-preview,.node-rewards{display:flex;flex-wrap:wrap;gap:5px;margin:12px 0;font-size:11px}.enemy-preview>strong,.node-rewards>strong{width:100%;font-size:12px}.enemy-preview>span,.node-rewards>span{padding:3px 5px;background:#e0e4cf}.node-rewards small{width:100%;color:#8c734f}.node-detail>.btn{width:100%;margin-top:10px}.node-detail>small,.atlas-footer small{display:block;margin-top:8px;color:var(--muted);font-size:10px;line-height:1.8}.locked-reason,.action-reason{color:#96603e}.tier-select{display:flex;align-items:center;justify-content:space-between;font-size:12px;margin-top:10px}.tier-select select{min-height:38px}.atlas-footer{display:grid;grid-template-columns:1fr 1fr;gap:24px;border-top:1px solid #b9b393;margin-top:18px;padding-top:18px}.atlas-footer h4{font-size:17px;margin:0 0 8px}.atlas-footer p{font-size:12px;line-height:1.9;color:var(--muted);margin:0 0 10px}.sect-sheet{margin-top:20px;padding-top:16px;border-top:1px solid #b9b393}.sect-sheet>.btn{margin-bottom:16px}
@media(max-width:860px){.atlas-layout{grid-template-columns:1fr}.map-board{height:470px}.node-detail{display:block}.atlas-footer{gap:16px}}
@media(max-width:520px){.atlas-heading{align-items:flex-start;flex-direction:column}.atlas-heading h3{font-size:23px}.region-switch button{flex:1;padding:10px 8px;font-size:14px}.region-intro>span{display:none}.map-board{height:430px}.map-node{width:64px}.node-name{max-width:64px;font-size:8px}.node-mark{width:26px;height:28px;font-size:14px}.area-label strong{font-size:12px}.area-label small{font-size:8px}.atlas-footer{grid-template-columns:1fr}.atlas-footer>div+div{border-top:1px solid #d2c7a9;padding-top:14px}}
</style>
