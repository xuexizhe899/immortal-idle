<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { GameState } from '../api/client'
import { characterImage } from '../presentation/assetPaths'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import BattleStage from '../rendering/BattleStage.vue'
import { useGameStore } from '../stores/game'

defineEmits<{ returnCity: [] }>()
const store = useGameStore()
const run = computed(() => store.state?.active_run)
const sect = computed(() => run.value?.party_snapshot?.mode.sect as GameState['sects'][number] | undefined)
const combatants = computed(() => run.value?.party_snapshot?.combatants ?? [])
const selected = ref<string[]>([])
const playing = ref(false)
const confirmRetreat = ref(false)
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
watch([() => run.value?.run_seed, () => run.value?.last_battle?.id], () => {
  const preferred = run.value?.selected_party.length ? run.value.selected_party : run.value?.party.slice(0, 3) ?? []
  selected.value = preferred.filter(id => (run.value?.member_hp[id] ?? 0) > 0)
  confirmRetreat.value = false
}, { immediate: true })
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
        <span class="eyebrow">宗门征讨 · {{ sect.style }}</span>
        <h2>{{ sect.name }}</h2>
        <p class="muted">{{ ended ? '本次征讨已结束，等待结算' : boss ? '守备已破，宗主应战' : '选定三位同道，迎战守擂弟子' }} · 进度自动保存</p>
      </div>
      <button class="btn btn-small" :disabled="store.busy" @click="$emit('returnCity')">返回宗门</button>
    </header>
    <section class="siege-progress" aria-label="宗门守备">
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
    </section>
    <div class="conquest-layout">
      <div>
        <BattleStage
          setting="sect"
          :party="stageParty"
          :result="store.battleResult"
          :bond-names="bondNames"
          @playing="playing=$event"
        />
        <section v-if="!ended" class="arena-selection">
          <div class="section-heading">
            <h3>{{ boss ? '选择决战弟子' : '安排本轮上阵' }}</h3>
            <span class="badge">{{ selected.length }} / 3 人</span>
          </div>
          <p class="muted">可重复上阵，气血延续。倒下者本次无法继续；选择顺序决定同身法时的优先次序。</p>
          <div class="fighter-grid">
            <button
              v-for="unit in combatants"
              :key="unit.id"
              :aria-pressed="selected.includes(unit.id)"
              :disabled="store.busy||playing||!(run.member_hp[unit.id]??0)"
              :class="{selected:selected.includes(unit.id),fallen:!(run.member_hp[unit.id]??0)}"
              @click="toggle(unit.id)"
            >
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
            @click="store.fightArena([...selected])"
          >
            {{ boss ? '挑战宗主' : '开始第 '+(run.arena_round+1)+' 轮擂台' }}
          </button>
          <div class="retreat-control">
            <template v-if="confirmRetreat">
              <p>撤退不会获得攻克奖励，行动力不退还；交战过的弟子会增加伤势。</p>
              <button class="btn btn-small" :disabled="store.busy||playing" @click="store.retreat()">确认撤退</button>
              <button class="btn btn-small btn-quiet" @click="confirmRetreat=false">继续征讨</button>
            </template>
            <button
              v-else
              class="btn btn-small btn-quiet"
              :disabled="store.busy||playing"
              @click="confirmRetreat=true"
            >
              撤回宗门
            </button>
          </div>
        </section>
        <section v-else class="conquest-ending">
          <span class="ending-seal">{{ store.status==='cleared'?'克':'归' }}</span>
          <h3>{{ store.status==='cleared' ? '山门已定，同道凯旋' : '暂收旗鼓，养锐再来' }}</h3>
          <p>{{ store.status==='cleared' ? '结算后领取攻克奖励，并可在远行码头安排弟子驻守。' : reason+' 本次没有攻克奖励；结算后可查看伤势并重新整备。' }}</p>
          <button class="btn btn-primary" :disabled="store.busy||playing" @click="store.settleRun()">结算并返回宗门</button>
        </section>
      </div>
      <aside>
        <section v-if="!ended" class="opponent-panel">
          <span class="eyebrow">下一场交锋</span>
          <h3>{{ boss ? '镇宗宗主' : '第 '+(run.arena_round+1)+' 轮守擂弟子' }}</h3>
          <article v-for="enemy in opponents" :key="enemy.id">
            <img :src="characterImage(enemy.asset_id)" alt="" class="pixel-art" />
            <div>
              <strong>{{ enemy.name }}</strong>
              <small>气血 {{ enemy.health }} · 攻击 {{ number(enemy.attack,1) }}</small>
            </div>
            <p>{{ enemy.active.name }} · {{ enemy.active.description }}</p>
            <p v-if="enemy.passive.description">{{ enemy.passive.name }} · {{ enemy.passive.description }}</p>
          </article>
        </section>
        <section class="spoils-panel">
          <span class="eyebrow">攻克后带回</span>
          <h3>宗门战利品</h3>
          <div v-for="(amount,id) in sect.loot" :key="id">
            <span>{{ resourceName(id,store.catalog) }}</span>
            <strong>{{ number(amount,1) }}</strong>
          </div>
          <p class="muted">
            击败宗主后一次领取。攻克后可驻守获取
            {{ resourceName(sect.material_id,store.catalog) }}
            与
            {{ resourceName(sect.special_material_id,store.catalog) }}
            。
          </p>
        </section>
        <p class="guard-rule">守备削减只看本场获胜后的存活人数：三人 50、两人 30、一人 15。守备归零即进入宗主决战。</p>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.conquest-page{max-width:1400px;margin:auto;padding:28px 36px 48px}.conquest-heading{display:flex;align-items:center;justify-content:space-between;gap:18px}.conquest-heading h2{font-size:30px;margin:6px 0}.conquest-heading p{font-size:12px;margin:0}.siege-progress{margin:24px 0;padding:17px 22px;border:1px solid #b5bfa0;background:#e2e8d4;display:grid;grid-template-columns:150px 1fr;gap:9px 24px;align-items:center}.siege-progress>div:first-child{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px}.siege-progress strong{font:25px 'SimSun',serif;color:var(--jade)}.siege-progress strong small{font-size:11px;color:var(--muted)}.guard-track{height:9px;background:#bfc8ae;box-shadow:inset 0 1px 2px #334a3826}.guard-track>span{display:block;height:100%;background:#68836b}.siege-progress p{grid-column:2;font-size:11px;margin:0;color:var(--muted)}.siege-progress .badge{margin-left:12px}.conquest-layout{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:24px}.arena-selection{margin-top:22px;border:1px solid #c5b993;background:#f3eddb;padding:21px}.arena-selection h3{font-size:22px}.arena-selection>.muted{font-size:11px;line-height:1.8}.fighter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.fighter-grid>button{position:relative;text-align:left;padding:9px;border:1px solid #c1baa0;background:#ebe8d7}.fighter-grid>button.selected{border-color:var(--jade);box-shadow:inset 0 0 0 1px var(--jade);background:#dfe7d1}.fighter-grid img{display:block;width:100%;height:105px;object-fit:contain;object-position:center 20%}.fighter-name{display:block;font:16px 'SimSun',serif;margin:6px 0}.fighter-name small{display:block;font:10px sans-serif;color:var(--gold);margin-top:5px}.fighter-hp{font-size:10px;color:var(--muted)}.fighter-track{display:block;height:4px;background:#c2c7af;margin-top:6px}.fighter-track i{display:block;background:var(--jade);height:100%}.fighter-grid .fallen{filter:grayscale(1);opacity:.6}.fight-button{width:100%}.retreat-control{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center}.retreat-control p{width:100%;font-size:11px;color:var(--danger);margin:4px 0}.conquest-layout aside>section{padding:18px;background:#f1ead6;border:1px solid #c7b992;margin-bottom:16px}.conquest-layout aside h3{font-size:19px;margin:5px 0 14px}.opponent-panel article{display:grid;grid-template-columns:46px 1fr;gap:5px 9px;padding:12px 0;border-top:1px solid #d8c9a6}.opponent-panel img{width:46px;height:60px;object-fit:contain;grid-row:1 / 3}.opponent-panel strong{font:15px 'SimSun',serif}.opponent-panel small{display:block;color:var(--muted);font-size:9px;margin-top:5px}.opponent-panel p{grid-column:1 / -1;font-size:10px;line-height:1.7;color:var(--muted);margin:3px 0}.spoils-panel>div{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #d8c9a6;font-size:11px}.spoils-panel strong{color:var(--jade);font-weight:500}.spoils-panel p,.guard-rule{font-size:10px;line-height:1.8;color:var(--muted)}.conquest-ending{text-align:center;padding:30px 22px;background:#f5edda;border:1px solid #c3b285;margin-top:22px}.ending-seal{display:inline-block;font:36px 'SimSun',serif;color:var(--gold);border:1px solid #ae9360;padding:2px 9px}.conquest-ending h3{font-size:25px;margin:14px 0}.conquest-ending p{font-size:12px;line-height:1.8;color:var(--muted)}.conquest-ending .btn{margin-top:10px}@media(max-width:850px){.conquest-page{padding:20px}.conquest-layout{grid-template-columns:1fr}.conquest-layout aside{display:grid;grid-template-columns:1fr 1fr;gap:12px}.guard-rule{grid-column:1 / -1}.conquest-layout aside>section{margin:0}}@media(max-width:540px){.conquest-page{padding:18px 12px 32px}.conquest-heading h2{font-size:25px}.conquest-heading p{font-size:10px}.siege-progress{padding:13px;grid-template-columns:1fr;gap:9px}.siege-progress p{grid-column:1}.arena-selection{padding:14px}.fighter-grid{gap:6px}.fighter-grid>button{padding:6px}.fighter-grid img{height:80px}.fighter-name{font-size:14px}.conquest-layout aside{grid-template-columns:1fr}.fighter-hp{font-size:9px}.conquest-ending .btn{width:100%}}
</style>
