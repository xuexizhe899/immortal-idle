<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { BattleResult } from '../api/client'
import { battleUnitsAt, effectLabel, playbackIndices, type BattleEvent, type BattleUnit } from './battlePlayback'
import EnemyFigure from './EnemyFigure.vue'
import SkillVfx from './SkillVfx.vue'

const props = defineProps<{
  party: { id: string; name: string; image: string }[]
  result: BattleResult | null
  bondNames?: Record<string, string>
}>()
const emit = defineEmits<{ playing: [value: boolean] }>()
const playing = ref(false)
const cursor = ref(Number.MAX_SAFE_INTEGER)
const speed = ref(2)
const mode = ref<'key' | 'all'>('key')
const reduced = ref(false)
const failedImages = ref<Set<string>>(new Set())
const sceneFailed = ref(false)
let timer: number | undefined
let watchdog: number | undefined
let motionQuery: MediaQueryList | undefined
let playbackToken = 0
const event = computed(() => props.result?.events[cursor.value] ?? null)
const units = computed(() => props.result ? battleUnitsAt(props.result, cursor.value) : [])
const armies = computed(() => [
  { side: 'ally', name: '门下同道', units: units.value.filter(unit => unit.side === 'ally').sort((a, b) => a.slot - b.slot) },
  { side: 'enemy', name: '守塔灵卫', units: units.value.filter(unit => unit.side === 'enemy').sort((a, b) => a.slot - b.slot) },
])
const latestEvents = computed(() => props.result?.events.slice(Math.max(0, Math.min(cursor.value + 1, props.result.events.length) - 4), Math.min(cursor.value + 1, props.result.events.length)) ?? [])
const outcome = computed(() => !props.result ? '同道已集结，静候前行' : props.result.reason === 'round_limit' ? '回合已尽，此行暂歇' : props.result.won ? '此战获胜' : '此战失利')
const nameById = computed(() => new Map(props.result?.initial_units.map(unit => [unit.id, unit.name]) ?? []))
function image(unit: BattleUnit): string {
  const known = props.party.find(member => member.id === unit.id)?.image
  if (known) return known
  return unit.asset_id ? `/assets/${unit.asset_id}${unit.asset_id.endsWith('.png') ? '' : '.png'}` : ''
}
function markBroken(id: string) { failedImages.value = new Set([...failedImages.value, id]) }
function effectsFor(id: string) { return event.value?.effects.filter(effect => effect.target_id === id) ?? [] }
function isTarget(id: string) { return playing.value && !!effectsFor(id).length }
function stateText(unit: BattleUnit) {
  return unit.statuses.filter(status => status.kind === 'buff').map(status => {
    const name: Record<string, string> = { atk: '攻', def: '防', spd: '速' }
    return `${name[status.stat] ?? status.stat}${status.value >= 0 ? '↑' : '↓'}`
  }).join(' · ')
}
function statusDetails(unit: BattleUnit) {
  return unit.statuses.map(status => status.kind === 'shield'
    ? `护盾 ${status.remaining}，第${status.expires_round}轮开始消退`
    : `${({ atk: '攻击', def: '防御', spd: '身法' } as Record<string, string>)[status.stat] ?? status.stat} ${status.value >= 0 ? '+' : ''}${Math.round(status.value * 100)}%，第${status.expires_round}轮开始消退`).join('；')
}
function eventText(item: BattleEvent) {
  const actor = nameById.value.get(item.actor_id) ?? item.actor_id
  return `${actor} · ${item.skill_name}：${item.effects.map(effect => `${nameById.value.get(effect.target_id) ?? effect.target_id} ${effectLabel(effect)}`).join('；') || '本次行动结束'}`
}
function clearTimers() {
  if (timer !== undefined) window.clearTimeout(timer)
  if (watchdog !== undefined) window.clearTimeout(watchdog)
  timer = undefined
  watchdog = undefined
}
function finish() {
  playbackToken += 1
  clearTimers()
  cursor.value = props.result?.events.length ?? 0
  playing.value = false
  emit('playing', false)
}
function play() {
  finish()
  if (!props.result?.events.length || reduced.value || document.hidden) return
  const indices = playbackIndices(props.result.events, mode.value)
  const token = ++playbackToken
  let step = 0
  cursor.value = -1
  playing.value = true
  emit('playing', true)
  // 摘要最多十帧。后台切换、异常及卸载均释放操作，不依赖图片加载完成。
  watchdog = window.setTimeout(finish, mode.value === 'key' ? 14_000 : 180_000)
  const next = () => {
    if (token !== playbackToken) return
    if (step >= indices.length) { finish(); return }
    cursor.value = indices[step++]!
    timer = window.setTimeout(next, (mode.value === 'key' ? 850 : 600) / speed.value)
  }
  next()
}
function visibility() { if (document.hidden && playing.value) finish() }
function motionChanged() {
  reduced.value = motionQuery?.matches ?? false
  if (reduced.value) finish()
}
watch(() => props.result?.id, (id, previous) => {
  failedImages.value = new Set()
  if (id && previous !== id) play()
  else if (!id) finish()
})
onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionChanged()
  motionQuery.addEventListener('change', motionChanged)
  document.addEventListener('visibilitychange', visibility)
})
onUnmounted(() => {
  finish()
  motionQuery?.removeEventListener('change', motionChanged)
  document.removeEventListener('visibilitychange', visibility)
})
</script>
<template>
  <section class="battle-stage" aria-label="问道塔交锋">
    <img v-if="!sceneFailed" class="stage-scene pixel-art" src="/assets/trial-v03/scene_tower_trial.png" alt="" draggable="false" @error="sceneFailed = true" />
    <div class="stage-veil"></div>
    <header class="stage-caption"><span class="eyebrow">问道塔 · 同道试炼</span><span>{{ playing && event ? `第 ${event.round} 轮 · ${event.skill_name}` : outcome }}</span></header>
    <div v-if="result" class="battle-armies">
      <section v-for="army in armies" :key="army.side" class="army" :class="army.side" :aria-label="army.name">
        <h4>{{ army.name }} <small>{{ army.units.filter(unit => unit.hp > 0).length }} / {{ army.units.length }}</small></h4>
        <div class="combatants">
          <article v-for="unit in army.units" :key="unit.id" :class="['combatant', { fallen: unit.hp === 0, acting: playing && event?.actor_id === unit.id, targeted: isTarget(unit.id) }]" :aria-label="`${unit.name}，气血${unit.hp}/${unit.max_hp}，护盾${unit.shield}`">
            <div class="unit-portrait">
              <img v-if="unit.side === 'ally' && image(unit) && !failedImages.has(unit.id)" :src="image(unit)" alt="" class="pixel-art" decoding="async" draggable="false" @error="markBroken(unit.id)" />
              <EnemyFigure v-else :kind="unit.side === 'enemy' ? unit.template_id : 'warden'" />
              <span class="unit-slot">{{ unit.slot + 1 }}</span>
              <span v-if="unit.hp === 0" class="fallen-label">暂歇</span>
              <SkillVfx v-if="isTarget(unit.id)" :key="`${event?.sequence}-${unit.id}`" :kind="event?.vfx ?? 'strike'" :defensive="effectsFor(unit.id).some(effect => effect.kind === 'heal' || effect.kind === 'shield')" />
              <div v-if="isTarget(unit.id)" class="effect-numbers"><span v-for="(effect,index) in effectsFor(unit.id)" :key="index" :class="effect.kind">{{ effectLabel(effect) }}</span></div>
            </div>
            <div class="unit-name"><strong>{{ unit.name }}</strong><span v-if="unit.cooldown">冷却 {{ unit.cooldown }}</span><span v-else class="ready">就绪</span></div>
            <div class="unit-health"><i :style="{ width: `${unit.hp / Math.max(1,unit.max_hp) * 100}%` }"></i></div>
            <small class="unit-vitals">{{ unit.hp }}/{{ unit.max_hp }}<b v-if="unit.shield"> · 盾 {{ unit.shield }}</b></small>
            <span class="unit-status" :title="statusDetails(unit)">{{ stateText(unit) || ' ' }}</span>
          </article>
        </div>
      </section>
    </div>
    <div v-else class="waiting-party"><div v-for="member in party" :key="member.id"><img v-if="!failedImages.has(member.id)" :src="member.image" alt="" class="pixel-art" decoding="async" @error="markBroken(member.id)" /><EnemyFigure v-else kind="warden" /><strong>{{ member.name }}</strong></div><p v-if="!party.length">等待同道入场</p></div>
    <div v-if="result" class="battle-controls">
      <span class="battle-outcome" :class="{ lost: !result.won }">{{ playing ? '交锋' : result.won ? '获胜' : '暂歇' }}<small>{{ result.rounds }} 轮 · {{ result.events.length }} 次行动</small></span>
      <label>演出<select v-model="mode" :disabled="playing"><option value="key">关键招式</option><option value="all">完整交锋</option></select></label>
      <label>速度<select v-model="speed"><option :value="1">1×</option><option :value="2">2×</option></select></label>
      <button v-if="playing" class="btn btn-small" @click="finish">跳过演出</button><button v-else class="btn btn-small" :disabled="reduced || !result.events.length" @click="play">重播此战</button>
      <p v-if="reduced" class="motion-note">已按减少动态效果偏好展示战果，可展开完整战报。</p>
      <p class="battle-totals">同道实际承伤 {{ result.damage }} · 恢复 {{ result.healed }} · 战后气血 {{ result.hp_after }}</p>
    </div>
    <div v-if="result" class="battle-log">
      <p class="current-action" aria-live="polite">{{ playing && event ? `${nameById.get(event.actor_id)} · ${event.skill_name}` : outcome }}<span v-if="playing && event?.bonds.length" class="bond-flare">{{ event.bonds.map(id => bondNames?.[id] ?? id).join(' · ') }}</span></p>
      <ol class="recent-events"><li v-for="item in latestEvents" :key="item.sequence"><small>第{{ item.round }}轮</small>{{ eventText(item) }}<b v-for="id in item.bonds" :key="id">{{ bondNames?.[id] ?? id }}</b></li></ol>
      <details><summary>完整战报 · {{ result.events.length }} 次行动</summary><ol class="full-events"><li v-for="item in result.events" :key="item.sequence"><small>第{{ item.round }}轮</small>{{ eventText(item) }}<b v-for="id in item.bonds" :key="id">{{ bondNames?.[id] ?? id }}</b></li></ol></details>
    </div>
    <p v-else class="stage-bottom">选择前方路线，招式就绪时同道会自动施展。</p>
  </section>
</template>
<style scoped>
.battle-stage{position:relative;overflow:hidden;background:#d5ddc6;border:1px solid #b7bba0}.stage-scene{position:absolute;inset:0;width:100%;height:490px;object-fit:cover;object-position:center 65%;opacity:.6;pointer-events:none}.stage-veil{position:absolute;inset:0;background:linear-gradient(#edf0dc35,#e2e8d0aa 440px,#f5efdf 550px);pointer-events:none}.stage-caption{position:relative;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;color:#385940;font-size:11px}.stage-caption .eyebrow{font-size:9px;background:#faf4dfd9;padding:4px 7px}.battle-armies{position:relative;display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 18px 16px}.army{min-width:0}.army h4{font:15px 'SimSun',serif;margin:0 0 8px;color:#3d604a;border-bottom:1px solid #7b917b66;padding-bottom:5px}.enemy h4{color:#805d3f}.army h4 small{float:right;font:10px system-ui}.combatants{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 8px}.combatant{position:relative;min-width:0;padding:3px 4px;background:#f4efdbc9;border:1px solid #b3bea3;transition:background .12s}.enemy .combatant{background:#e7e4d5c9;border-color:#b3ad91}.combatant.acting{border-color:#9c7a39;box-shadow:inset 0 0 0 2px #c3a75c}.combatant.targeted{background:#fff7d9}.unit-portrait{position:relative;height:94px;display:flex;align-items:flex-end;justify-content:center}.unit-portrait>img{width:100%;height:100%;object-fit:contain;object-position:center 25%}.unit-portrait>.enemy-figure{height:94px;width:85px}.unit-slot{position:absolute;top:1px;left:1px;font-size:8px;color:#66785e}.unit-name{display:flex;justify-content:space-between;gap:2px;align-items:center;font-size:9px}.unit-name strong{font:12px 'SimSun',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.unit-name>span{font-size:8px;white-space:nowrap;color:#8b7651}.unit-name .ready{color:#597b5f}.unit-health{height:4px;background:#a9ad93;margin-top:4px;overflow:hidden}.unit-health i{display:block;height:100%;background:#538465;transition:width .18s}.enemy .unit-health i{background:#9b7958}.unit-vitals{display:block;font-size:8px;color:#4b634b;white-space:nowrap;font-variant-numeric:tabular-nums}.unit-vitals b{font-weight:400;color:#426f88}.unit-status{font-size:8px;color:#8c6348;display:block;min-height:12px}.fallen{filter:grayscale(.7);opacity:.62}.fallen-label{position:absolute;bottom:20px;color:#eee4ca;background:#52634be0;font:14px 'SimSun',serif;padding:2px 8px}.effect-numbers{position:absolute;top:24%;left:0;right:0;z-index:2;display:flex;align-items:center;flex-direction:column;gap:3px;font-size:11px;font-weight:700;color:#8e3f2f;text-shadow:0 1px #fff7df,1px 0 #fff7df,-1px 0 #fff7df}.effect-numbers>span{background:#f6efdbd9;padding:1px 3px}.effect-numbers .heal{color:#286848}.effect-numbers .shield{color:#386e83}.effect-numbers .buff{color:#805b30}.battle-controls{position:relative;display:flex;align-items:center;gap:12px;padding:12px 16px;background:#f7f0de;border-block:1px solid #b9baa0;flex-wrap:wrap}.battle-outcome{font:19px 'SimSun',serif;color:var(--jade);margin-right:auto}.battle-outcome small{display:block;font:9px system-ui;color:var(--muted);margin-top:4px}.battle-outcome.lost{color:var(--danger)}.battle-controls label{font-size:9px;color:var(--muted)}.battle-controls select{display:block;margin-top:2px;font-size:10px;min-height:32px;padding:4px 18px 4px 5px}.battle-controls .btn{min-height:36px;font-size:11px}.battle-totals{width:100%;font-size:10px;color:#68755b;margin:0}.motion-note{width:100%;font-size:10px;margin:0;color:var(--muted)}.battle-log{position:relative;background:#f3efdf;padding:10px 16px}.current-action{margin:0 0 7px;font-size:12px;color:var(--jade)}.bond-flare{display:inline-block;margin-left:8px;padding:1px 6px;border:1px solid #bca668;color:#86632c;font-size:10px}.recent-events,.full-events{list-style:none;padding:0;margin:0;font-size:10px;color:#596951}.recent-events{min-height:64px}.recent-events li,.full-events li{padding:3px 0;border-top:1px solid #d3d3bc;overflow-wrap:anywhere}.battle-log li small{font-size:8px;margin-right:6px;color:#8b8a6d}.battle-log li b{display:inline-block;margin-left:5px;color:#96702c;font-weight:500}.battle-log details{margin-top:8px;font-size:10px}.battle-log summary{cursor:pointer;padding:6px 0;color:#6c775c}.full-events{max-height:300px;overflow-y:auto}.waiting-party{position:relative;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;min-height:200px;align-items:end;padding:25px 20px}.waiting-party>div{min-width:0;text-align:center}.waiting-party img,.waiting-party .enemy-figure{width:100%;height:145px;object-fit:contain}.waiting-party strong{display:block;font:12px 'SimSun',serif;color:#3e5f46}.stage-bottom{position:relative;text-align:center;font-size:11px;color:var(--muted);margin:0;padding:12px;background:#f5efdfe0}
@media(max-width:640px){.stage-caption{padding:10px;gap:6px;font-size:9px}.stage-caption .eyebrow{font-size:8px}.battle-armies{grid-template-columns:1fr;gap:14px;padding:0 12px 14px}.army h4{font-size:13px}.combatants{gap:7px}.unit-portrait{height:80px}.unit-portrait>.enemy-figure{height:80px;width:72px}.unit-name strong{font-size:12px}.unit-vitals{font-size:9px}.unit-name>span{font-size:9px}.unit-status{font-size:9px}.battle-controls{gap:8px;padding:10px}.battle-controls select{min-height:36px}.battle-controls .btn{font-size:10px;padding-inline:8px}.battle-outcome{font-size:17px}.battle-outcome small{font-size:8px}.battle-log{padding:10px}.recent-events,.full-events{font-size:10px}.waiting-party{grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:10px 15px}.waiting-party img,.waiting-party .enemy-figure{height:100px}.stage-scene{height:700px}.effect-numbers{font-size:10px}}
@media(prefers-reduced-motion:reduce){.unit-health i,.combatant{transition:none}}
</style>
