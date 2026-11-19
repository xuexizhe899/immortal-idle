<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { GameState } from '../api/client'
import { characterImage } from '../presentation/assetPaths'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import BattleStage from '../rendering/BattleStage.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import { useGameStore } from '../stores/game'

defineEmits<{ returnCity: [] }>()
const store = useGameStore()
const run = computed(() => store.state?.active_run)
const sect = computed(() => run.value?.party_snapshot?.mode.sect as GameState['sects'][number] | undefined)
const combatants = computed(() => run.value?.party_snapshot?.combatants ?? [])
const selected = ref<string[]>([])
const playing = ref(false)
const detailPanel = ref('')
const detailTitles: Record<string, string> = { formation: '安排上阵', opponents: '下场敌情', spoils: '此行战利品', retreat: '确认撤回宗门' }
const ended = computed(() => store.status === 'cleared' || store.status === 'defeated')
const boss = computed(() => run.value?.guard === 0)
const opponents = computed(() => {
  if (!sect.value) return []
  return boss.value ? [sect.value.leader] : sect.value.arena_teams[run.value?.arena_round ?? 0] ?? []
})
const stageParty = computed(() => combatants.value
  .filter(unit => store.battleResult || selected.value.includes(unit.id))
  .map(unit => ({ id: unit.id, name: unit.name, image: characterImage(unit.asset_id) })),
)
const bondNames = computed(() => Object.fromEntries(
  (run.value?.party_snapshot?.bonds ?? []).map(bond => [bond.id, bond.name]),
))
const endReasons: Record<string, string> = {
  guard_unbroken: '三轮擂台结束，尚未攻破宗门守备。',
  insufficient_fighters: '能继续上阵的弟子不足三人。',
  round_limit: '二十轮内未能击败宗主。',
  retreated: '本次征讨已撤回。',
  defeated: '宗主决战失利。',
}
const reason = computed(() => endReasons[run.value?.end_reason ?? ''] ?? '本次征讨已经结束。')
const selectedUnits = computed(() => selected.value.map(id => combatants.value.find(unit => unit.id === id)))
const availableCount = computed(() => combatants.value.filter(unit => (run.value?.member_hp[unit.id] ?? 0) > 0).length)
const selectionHint = computed(() => {
  if (playing.value) return '正在播放交锋，可在战场中跳过后安排下一场。'
  if (store.busy) return '正在确认本次操作，请稍候。'
  if (availableCount.value < 3) return `目前仅有 ${availableCount.value} 位同道可战，无法组成三人阵容。`
  if (selected.value.length < 3) return `还需选择 ${3 - selected.value.length} 位同道，选齐后即可出战。`
  return '三位同道已就位。更换人选时，先点已选弟子将其移出。'
})
watch([() => store.slotId, () => run.value?.run_seed, () => run.value?.last_battle?.id], () => {
  const preferred = run.value?.selected_party.length ? run.value.selected_party : run.value?.party.slice(0, 3) ?? []
  selected.value = preferred.filter(id => (run.value?.member_hp[id] ?? 0) > 0)
  detailPanel.value = ''
}, { immediate: true })
watch([ended, playing], ([complete, active]) => { if (complete || active) detailPanel.value = '' })
function openDetail(panel: string) {
  if (store.busy || ((playing.value || ended.value) && ['formation', 'retreat'].includes(panel))) return
  detailPanel.value = panel
}
async function fight() {
  if (store.busy || playing.value || ended.value || selected.value.length !== 3) return
  await store.fightArena([...selected.value])
}
function toggle(id: string) {
  if (store.busy || playing.value || ended.value || !(run.value?.member_hp[id] ?? 0)) return
  if (selected.value.includes(id)) {
    selected.value = selected.value.filter(member => member !== id)
  } else if (selected.value.length < 3) {
    selected.value = [...selected.value, id]
  }
}
</script>

<template>
  <main v-if="run && sect" class="conquest-page">
    <header class="conquest-heading">
      <div>
        <span class="eyebrow">{{ run.is_retrial ? '宗门论道' : '宗门征讨' }} · {{ sect.style }}</span>
        <h2>{{ sect.name }}</h2>
        <p class="muted">{{ ended ? (run.is_retrial ? '本次论道已结束，等待结算' : '本次征讨已结束，等待结算') : boss ? (run.is_retrial ? '单场论道，宗主应战' : '守备已破，宗主应战') : '选定三位同道，迎战守擂弟子' }} · 进度自动保存</p>
      </div>
      <button class="btn btn-small" :disabled="store.busy" @click="$emit('returnCity')">返回宗门</button>
    </header>
    <section v-if="!run.is_retrial" class="siege-progress" aria-label="宗门守备">
      <div>
        <span>宗门守备</span>
        <strong>
          {{ run.guard }}
          <small>/ 100</small>
        </strong>
      </div>
      <div class="guard-track">
        <span :style="{width:run.guard+'%'}"></span>
      </div>
      <p>
        已进行
        {{ run.arena_round }}
        / 3 轮擂台
        <span class="badge" :class="{'badge-gold':boss}">{{ boss ? '宗主决战 · 3v1' : '擂台交锋 · 3v3' }}</span>
      </p>
      <ol class="siege-stages" aria-label="征讨阶段"><li :class="{active:!boss&&!ended,done:boss}">削减守备</li><li :class="{active:boss&&!ended,done:store.status==='cleared'}">宗主决战</li><li :class="{active:ended}">带回战果</li></ol>
    </section>
        <section v-if="ended" class="conquest-ending">
          <span class="ending-seal">{{ store.status==='cleared'?(run.is_retrial?'论':'克'):'归' }}</span>
          <h3>{{ store.status==='cleared' ? (run.is_retrial ? '论道获胜，同道凯旋' : '山门已定，同道凯旋') : '暂收旗鼓，养锐再来' }}</h3>
          <p>{{ store.status==='cleared' ? (run.is_retrial ? '结算后领取论道奖励；不影响该宗门的驻守安排。' : '结算后领取攻克奖励，并可在远行码头安排弟子驻守。') : reason+(run.is_retrial ? ' 本次没有论道奖励；结算后可查看伤势并重新整备。' : ' 本次没有攻克奖励；结算后可查看伤势并重新整备。') }}</p>
          <button class="btn btn-primary" :disabled="store.busy||playing" @click="store.settleRun()">结算并返回宗门</button>
        </section>
    <section v-if="!ended" class="arena-toolbar" aria-label="本场交锋操作">
      <div><strong>{{ boss ? '宗主决战' : '第 '+(run.arena_round+1)+' 轮擂台' }}</strong><p role="status">{{ selectionHint }}</p><small>{{ selectedUnits.map(unit=>unit?.name??'').join(' · ') || '尚未安排上阵弟子' }}</small></div>
      <nav aria-label="交锋与详情"><button class="btn" :disabled="store.busy||playing" aria-haspopup="dialog" @click="openDetail('formation')">调整上阵 · {{ selected.length }}/3</button><button class="btn btn-primary" :disabled="store.busy||playing||selected.length!==3" @click="fight">{{ boss?'挑战宗主':'开始交锋' }}</button><button class="btn btn-small btn-quiet" :disabled="store.busy" aria-haspopup="dialog" @click="openDetail('opponents')">下场敌情</button><button class="btn btn-small btn-quiet" :disabled="store.busy" aria-haspopup="dialog" @click="openDetail('spoils')">战利品</button><button class="btn btn-small btn-quiet" :disabled="store.busy||playing" aria-haspopup="dialog" @click="openDetail('retreat')">撤回宗门</button></nav>
    </section>
        <BattleStage
          setting="sect"
          :title="`${sect.name} · ${run.is_retrial?'宗门论道':'宗门擂台'}`"
          :party="stageParty"
          :result="store.battleResult"
          :bond-names="bondNames"
          @playing="playing=$event"
        />
    <button v-if="ended" class="btn btn-small ending-spoils" aria-haspopup="dialog" @click="openDetail('spoils')">查看战利品说明</button>
    <PanelModal v-if="detailPanel" :title="detailTitles[detailPanel] ?? '交锋详情'" :subtitle="sect.name" wide @close="detailPanel=''">
        <section v-if="detailPanel==='formation'" class="arena-selection">
          <div class="section-heading">
            <h3>{{ boss ? '选择决战弟子' : '安排本轮上阵' }}</h3>
            <span class="badge">{{ selected.length }} / 3 人</span>
          </div>
          <p class="muted">可重复上阵，气血延续。倒下者本次无法继续；选择顺序决定同身法时的优先次序。</p>
          <ol class="selected-lineup" aria-label="本场上阵顺序"><li v-for="slot in 3" :key="slot" :class="{filled:!!selectedUnits[slot-1]}"><b>{{ slot }}</b><strong>{{ selectedUnits[slot-1]?.name??'待选同道' }}</strong><span v-if="selectedUnits[slot-1]">气血 {{ run.member_hp[selectedUnits[slot-1]?.id??'']??0 }}</span><span v-else>点选下方弟子</span></li></ol>
          <p id="arena-selection-hint" class="selection-hint" :class="{locked:store.busy||playing}" role="status">{{ selectionHint }}</p>
          <div class="fighter-grid" aria-describedby="arena-selection-hint">
            <button
              v-for="unit in combatants"
              :key="unit.id"
              :aria-pressed="selected.includes(unit.id)"
              :disabled="store.busy||playing||!(run.member_hp[unit.id]??0)||(selected.length===3&&!selected.includes(unit.id))"
              :class="{selected:selected.includes(unit.id),fallen:!(run.member_hp[unit.id]??0)}"
              @click="toggle(unit.id)"
            >
              <span v-if="selected.includes(unit.id)" class="selection-order">{{ selected.indexOf(unit.id)+1 }}</span>
              <img :src="characterImage(unit.asset_id)" alt="" class="pixel-art" />
              <span class="fighter-name">
                {{ unit.name }}
                <small>
                  {{ selected.includes(unit.id) ? '第 '+(selected.indexOf(unit.id)+1)+' 位' : (run.member_hp[unit.id]??0)>0 ? '候战' : '倒下 · 停战' }}
                </small>
              </span>
              <span class="fighter-hp">{{ run.member_hp[unit.id] ?? 0 }} / {{ unit.health }}</span>
              <span class="fighter-track">
                <i :style="{width:((run.member_hp[unit.id]??0)/unit.health*100)+'%'}"></i>
              </span>
            </button>
          </div>
          <button
            class="btn btn-primary fight-button"
            :disabled="store.busy||playing||selected.length!==3"
            aria-describedby="arena-selection-hint"
            @click="fight"
          >
            {{ store.busy ? '正在确认…' : playing ? '演出结束后继续' : selected.length!==3 ? '还需选择 '+(3-selected.length)+' 位同道' : boss ? '挑战宗主' : '开始第 '+(run.arena_round+1)+' 轮擂台' }}
          </button>
        </section>
        <section v-else-if="detailPanel==='opponents'" class="opponent-panel">
          <span class="eyebrow">下一场交锋</span>
          <h3>{{ boss ? '镇宗宗主' : '第 '+(run.arena_round+1)+' 轮守擂弟子' }}</h3>
          <article v-for="enemy in opponents" :key="enemy.id">
            <img :src="characterImage(enemy.asset_id)" alt="" class="pixel-art" />
            <div>
              <strong>{{ enemy.name }}</strong>
              <small>气血 {{ enemy.health }} · 攻击 {{ number(enemy.attack,1) }}</small><small>防御 {{ number(enemy.defense,1) }} · 身法 {{ number(enemy.speed,1) }}</small>
            </div>
            <p>{{ enemy.active.name }} · {{ enemy.active.description }}</p>
            <p v-if="enemy.passive.description">{{ enemy.passive.name }} · {{ enemy.passive.description }}</p>
          </article>
        </section>
        <section v-else-if="detailPanel==='spoils'" class="spoils-panel">
          <span class="eyebrow">{{ run.is_retrial ? '论道所得' : '攻克后带回' }}</span>
          <h3>{{ run.is_retrial ? '论道奖励' : '宗门战利品' }}</h3>
          <div v-for="(amount,id) in (run.is_retrial ? run.retrial_reward : sect.loot)" :key="id">
            <span>{{ resourceName(id,store.catalog) }}</span>
            <strong>{{ number(amount,1) }}</strong>
          </div>
          <p class="muted">
            <template v-if="run.is_retrial">击败宗主后一次领取；失败无奖励，不影响驻守。</template>
            <template v-else>
              击败宗主后一次领取。攻克后可驻守获取
              {{ resourceName(sect.material_id,store.catalog) }}
              与
              {{ resourceName(sect.special_material_id,store.catalog) }}
              。
            </template>
          </p>
        <p v-if="!run.is_retrial" class="guard-rule">守备削减只看本场获胜后的存活人数：三人 50、两人 30、一人 15。守备归零即进入宗主决战。</p>
        </section>
        <section v-else class="retreat-control"><p>{{ run.is_retrial ? '撤退不会获得论道奖励，行动力不退还；交战过的弟子会增加伤势。' : '撤退不会获得攻克奖励，行动力不退还；交战过的弟子会增加伤势。' }}</p><button class="btn" @click="detailPanel=''">继续交锋</button><button class="btn btn-danger" :disabled="store.busy||playing||ended" @click="store.retreat()">确认撤退</button></section>
    </PanelModal>
  </main>
</template>

<style scoped>
.arena-toolbar{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 16px;margin:20px 0 14px;background:var(--surface-raised);border:1px solid #bac4a7}.arena-toolbar>div{min-width:0}.arena-toolbar strong{font:18px 'SimSun',serif;color:var(--jade)}.arena-toolbar p{font-size:12px;line-height:1.6;margin:5px 0;color:var(--muted)}.arena-toolbar small{font-size:11px;color:var(--gold)}.arena-toolbar nav{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px;max-width:430px}.arena-toolbar .btn{min-height:44px}.ending-spoils{margin-top:14px}
@media(max-width:640px){.arena-toolbar{align-items:stretch;flex-direction:column;gap:10px;padding:12px}.arena-toolbar nav{max-width:none;justify-content:flex-start}.arena-toolbar nav>.btn{flex:1 0 auto}.arena-selection .fighter-grid img{height:58px}.arena-selection .fighter-name{font-size:13px}.arena-selection .fighter-grid{margin-block:10px}}
.conquest-page{max-width:1400px;margin:auto;padding:28px 36px 48px}.conquest-heading{display:flex;align-items:center;justify-content:space-between;gap:18px}.conquest-heading h2{font-size:30px;margin:6px 0}.conquest-heading p{font-size:12px;margin:0}.siege-progress{margin:24px 0;padding:17px 22px;border:1px solid #b5bfa0;background:#e2e8d4;display:grid;grid-template-columns:150px 1fr;gap:9px 24px;align-items:center}.siege-progress>div:first-child{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px}.siege-progress strong{font:25px 'SimSun',serif;color:var(--jade)}.siege-progress strong small{font-size:11px;color:var(--muted)}.guard-track{height:9px;background:#bfc8ae;box-shadow:inset 0 1px 2px #334a3826}.guard-track>span{display:block;height:100%;background:#68836b}.siege-progress p{grid-column:2;font-size:11px;margin:0;color:var(--muted)}.siege-progress .badge{margin-left:12px}.arena-selection{margin:0;border:1px solid #c5b993;background:#f3eddb;padding:21px}.arena-selection h3{font-size:22px}.arena-selection>.muted{font-size:11px;line-height:1.8}.fighter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.fighter-grid>button{position:relative;text-align:left;padding:9px;border:1px solid #c1baa0;background:#ebe8d7}.fighter-grid>button.selected{border-color:var(--jade);box-shadow:inset 0 0 0 1px var(--jade);background:#dfe7d1}.fighter-grid img{display:block;width:100%;height:105px;object-fit:contain;object-position:center 20%}.fighter-name{display:block;font:16px 'SimSun',serif;margin:6px 0}.fighter-name small{display:block;font:10px sans-serif;color:var(--gold);margin-top:5px}.fighter-hp{font-size:10px;color:var(--muted)}.fighter-track{display:block;height:4px;background:#c2c7af;margin-top:6px}.fighter-track i{display:block;background:var(--jade);height:100%}.fighter-grid .fallen{filter:grayscale(1);opacity:.6}.fight-button{width:100%}.retreat-control{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center}.retreat-control p{width:100%;font-size:11px;color:var(--danger);margin:4px 0}.opponent-panel h3,.spoils-panel h3{font-size:19px;margin:5px 0 14px}.opponent-panel article{display:grid;grid-template-columns:46px 1fr;gap:5px 9px;padding:12px 0;border-top:1px solid #d8c9a6}.opponent-panel img{width:46px;height:60px;object-fit:contain;grid-row:1 / 3}.opponent-panel strong{font:15px 'SimSun',serif}.opponent-panel small{display:block;color:var(--muted);font-size:9px;margin-top:5px}.opponent-panel p{grid-column:1 / -1;font-size:10px;line-height:1.7;color:var(--muted);margin:3px 0}.spoils-panel>div{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #d8c9a6;font-size:11px}.spoils-panel strong{color:var(--jade);font-weight:500}.spoils-panel p,.guard-rule{font-size:10px;line-height:1.8;color:var(--muted)}.conquest-ending{text-align:center;padding:30px 22px;background:#f5edda;border:1px solid #c3b285;margin:20px 0}.ending-seal{display:inline-block;font:36px 'SimSun',serif;color:var(--gold);border:1px solid #ae9360;padding:2px 9px}.conquest-ending h3{font-size:25px;margin:14px 0}.conquest-ending p{font-size:12px;line-height:1.8;color:var(--muted)}.conquest-ending .btn{margin-top:10px}@media(max-width:850px){.conquest-page{padding:20px}}@media(max-width:540px){.conquest-page{padding:18px 12px 32px}.conquest-heading h2{font-size:25px}.conquest-heading p{font-size:10px}.siege-progress{padding:13px;grid-template-columns:1fr;gap:9px}.siege-progress p{grid-column:1}.arena-selection{padding:14px}.fighter-grid{gap:6px}.fighter-grid>button{padding:6px}.fighter-grid img{height:80px}.fighter-name{font-size:14px}.fighter-hp{font-size:9px}.conquest-ending .btn{width:100%}}
.siege-stages{grid-column:1 / -1;display:flex;list-style:none;margin:7px 0 0;padding:11px 0 0;border-top:1px solid #b9c4a6;gap:10px;font-size:11px;color:#88927c}.siege-stages li{display:flex;align-items:center;gap:8px;flex:1}.siege-stages li::before{content:'';width:6px;height:6px;flex:none;border:1px solid #9ba98b;transform:rotate(45deg)}.siege-stages li.active{color:var(--jade);font-weight:600}.siege-stages li.active::before{background:var(--jade);border-color:var(--jade)}.siege-stages li.done{color:#71845d}.siege-stages li.done::before{background:#9aae82;border-color:#9aae82}.selected-lineup{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));list-style:none;gap:8px;margin:16px 0 12px;padding:0}.selected-lineup li{display:grid;grid-template-columns:24px minmax(0,1fr);align-items:center;gap:3px 6px;padding:10px 8px;border:1px dashed #b9b99b;background:#e8e7d4;color:#7e846b}.selected-lineup li.filled{border-style:solid;border-color:#9bae89;background:#e1e8d2;color:var(--jade)}.selected-lineup b{grid-row:1 / 3;display:grid;place-items:center;width:22px;height:22px;background:#d5dcc2;color:#627b55;font:14px 'SimSun',serif}.selected-lineup strong{font:14px 'SimSun',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.selected-lineup li>span{font-size:9px;color:var(--muted)}.selection-hint{margin:0;padding:9px 11px;border-left:3px solid #7b9670;background:#e4e9d6;color:var(--jade);font-size:11px;line-height:1.8}.selection-hint.locked{border-color:#b59654;background:#f0e8d1;color:#7d663e}.selection-order{position:absolute;top:7px;left:7px;display:grid;place-items:center;width:23px;height:23px;background:var(--jade);border:1px solid #b3c4a5;color:#faf3df;font:15px 'SimSun',serif;z-index:1}.fighter-grid>button:disabled:not(.fallen){opacity:.78}.fighter-grid>button:hover:not(:disabled){border-color:var(--jade);background:#e2e8d3}.fighter-grid>button.selected .fighter-name small{color:var(--jade)}.fighter-grid>button.selected::after{content:'已选';position:absolute;top:9px;right:8px;color:var(--jade);font-size:10px}.opponent-panel article>div{min-width:0}.opponent-panel article strong{overflow-wrap:anywhere}.fight-button{margin-top:2px;min-height:44px}.conquest-heading>div{min-width:0}.conquest-heading h2{overflow-wrap:anywhere}.guard-track>span{transition:width .25s ease}
@media(max-width:540px){.selected-lineup{gap:5px}.selected-lineup li{padding:8px 5px;grid-template-columns:18px minmax(0,1fr);gap:3px 4px}.selected-lineup b{width:18px;height:20px;font-size:12px}.selected-lineup strong{font-size:12px}.selected-lineup li>span{font-size:9px}.selection-hint{font-size:12px}.fighter-name small{font-size:11px;line-height:1.6}.fighter-hp{font-size:10px}.fighter-grid>button.selected::after{top:8px;right:5px;font-size:9px}.selection-order{width:21px;height:22px;top:5px;left:5px}.opponent-panel p,.spoils-panel p,.guard-rule{font-size:12px;line-height:1.8}.opponent-panel small{font-size:11px}.siege-stages{gap:7px;font-size:11px}.siege-stages li{gap:5px}.conquest-heading .btn{flex:none}.retreat-control{gap:6px}.retreat-control p{font-size:12px}}
@media(prefers-reduced-motion:reduce){.guard-track>span{transition:none}}
</style>
