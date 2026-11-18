<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CityDock from '../components/game/CityDock.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { discipleImage } from '../presentation/assetPaths'
import { effectText, resourceName, type DisplayCatalog } from '../presentation/gameText'
import { pickNextAction, type NextAction } from '../presentation/nextAction'
import CityScene from '../rendering/hd2d/CityScene.vue'
import { projectCityActors } from '../rendering/hd2d/cityModel'
import { phases, useDayCycle } from '../rendering/dayCycle'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import CodexPanel from './CodexPanel.vue'
import CraftPanel from './CraftPanel.vue'
import DutyPanel from './DutyPanel.vue'
import SectPanel from './SectPanel.vue'
import PreparePanel from './PreparePanel.vue'
import ExpeditionPanel from './ExpeditionPanel.vue'
const emit = defineEmits<{ resumeRun: [] }>()
const store = useGameStore()
const { selection, phaseName, lighting } = useDayCycle()
const openPanel = ref<string | null>(null)
const focusedDiscipleId = ref('')
const preparationReturn = ref<'tower'|'expedition'|null>(null)
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const city = computed(() => catalog.value?.city)
const actors = computed(() => projectCityActors(store.state, templateId => ({
  name: catalog.value?.disciples[templateId]?.name ?? templateId,
  image: discipleImage(templateId, catalog.value),
})))
const buildings = computed(() => (city.value?.hotspots ?? []).map(spot => ({ id: spot.id, name: spot.name, status: `${statusOf(spot.panel)} · ${secondaryStatusOf(spot.panel)}` })))
const activeRun = computed(() => store.state?.active_run ?? null)
const runEnded = computed(() => store.status === 'cleared' || store.status === 'defeated')
const runStep = computed(() => (activeRun.value?.nodes.length ?? 0) + (runEnded.value || store.status === 'choosing_affix' ? 0 : 1))
const towerLabel = computed(() => activeRun.value?.mode === 'tower' ? runEnded.value ? '待结算' : '继续出征' : '问道')
const towerHint = computed(() => activeRun.value?.mode === 'expedition' ? '远行中 · 点击继续' : activeRun.value ? `第 ${runStep.value} 层 · ${runEnded.value ? '收取战利品' : '试炼未歇'}` : '登塔试炼')
const expeditionLabel = computed(() => activeRun.value?.mode === 'expedition' ? (runEnded.value ? '待结算' : '继续远行') : '远行')
const expeditionHint = computed(() => activeRun.value?.sect_id ? (activeRun.value.is_retrial ? '论道中 · 点击继续' : `守备 ${activeRun.value.guard} · ${runEnded.value ? '等待结算' : '宗门征讨中'}`) : activeRun.value ? '出征中 · 点击继续' : `已攻克 ${store.state?.sects.filter(sect=>sect.conquered).length ?? 0} / ${store.state?.sects.length ?? 0} 座宗门`)
const runLocation = computed(() => activeRun.value?.sect_id ? `${activeRun.value.is_retrial ? '论道' : '宗门征讨'} · ${runEnded.value ? '等待结算' : activeRun.value.guard===0 ? '等待挑战宗主' : '守备 '+activeRun.value.guard+' · 等待安排上阵'}` : runEnded.value ? `此次到达 ${runStep.value}${activeRun.value?.mode === 'expedition' ? ' 段' : ' 层'}，尚待结算` : store.status === 'choosing_affix' ? `第 ${activeRun.value?.nodes.length ?? 0}${activeRun.value?.mode === 'expedition' ? ' 段' : ' 层'}获胜，等待领悟道法` : `${activeRun.value?.mode === 'expedition' ? '第 ' + runStep.value + ' 段远行' : '第 ' + runStep.value + ' 层试炼'}，等待选择路线`)
const TITLES: Record<string,string> = { codex:'弟子堂', sect:'宗门主殿', expedition:'远行码头', duty:'值守编制', forge:'炼器炉', alchemy:'炼丹房', tower:'问道塔 · 出征准备' }
const injured = computed(() => store.disciples.filter(d => d.injury_stacks > 0).length)
const recruitable = computed(() => Object.entries(catalog.value?.disciples ?? {}).filter(([id,d]) => !(store.state?.unlocks ?? []).includes(id) && (store.resources?.reputation ?? 0) >= (d.unlock_cost?.reputation??0)).length)
const currentGoal = computed(() => {
  if (activeRun.value) return runEnded.value ? '收取此次出征战利品' : activeRun.value.mode === 'expedition' ? '继续远行码头行程' : '继续问道塔试炼'
  if (!store.disciples.length) return '招募首位门下弟子'
  if (store.state?.last_run_review && !store.state.last_run_review.victory) return '复盘上次出征，调整队伍'
  if (!store.state?.duty_slots.length) return '安排弟子值守'
  if (!store.state.tower_floor) return '开启首次问道试炼'
  const total = catalog.value?.mode.node_count ?? 0
  return total && store.state.tower_floor >= total ? '修炼弟子，巩固道途' : `向问道塔第 ${store.state.tower_floor + 1} 层进发`
})
const permanentBonuses = computed(() => Object.entries(store.state?.bonuses ?? {}).map(([stat,value]) => effectText({stat,value,mode:'add_pct'})))
function statusOf(panel: string) {
  switch(panel) {
    case 'sect': return currentGoal.value
    case 'codex': return `弟子 / 招贤 · 门下 ${store.disciples.length} 人`
    case 'duty': return `值守 ${store.state?.duty_slots.length ?? 0} / ${catalog.value?.rules.max_duty ?? 6}`
    case 'tower': return activeRun.value?.mode === 'expedition' ? '已有远行行程，点击继续' : activeRun.value ? `${runEnded.value ? '待结算' : '继续出征'} · 第 ${runStep.value} 层` : `最高记录 ${store.state?.tower_floor ?? 0} 层`
    case 'expedition': return expeditionHint.value
    case 'alchemy': return `伤员 ${injured.value} 人 · 炼丹房 ${store.state?.facility_levels.alchemy ?? 1} 级`
    case 'forge': return `炼器炉 ${store.state?.facility_levels.forge ?? 1} 级 · 器具与专武培养`
    default: return '尚未开放'
  }
}
function secondaryStatusOf(panel: string) {
  switch(panel) {
    case 'sect': return store.lastSettle && store.lastSettle.elapsed_hours >= .05 ? `离线收益已收取 ${number(store.lastSettle.elapsed_hours,1)} 小时 · 存档管理` : '设施升级 · 离线收益 · 存档管理'
    case 'codex': return recruitable.value ? `${recruitable.value} 位贤才可招募` : '查看道法与同道羁绊'
    case 'duty': return `修为 +${number(store.production.cultivation,1)}/时 · 灵石 +${number(store.production.spirit_stone,1)}/时`
    case 'tower': return activeRun.value ? `最高记录 ${store.state?.tower_floor ?? 0} 层 · 队伍已锁定` : `${catalog.value?.mode.node_count ?? 0} 层试炼 · 行动力 ${catalog.value?.mode.stamina_cost ?? 1}`
    case 'expedition': return activeRun.value ? '当前已有出征，先完成或结算后再启程' : '宗门擂台 · 攻克驻守 · 2 行动力'
    case 'alchemy': return '疗伤丹药 · 永久增益'
    case 'forge': return permanentBonuses.value.length ? `永久 ${permanentBonuses.value.slice(0,2).join(' · ')}` : '炼制法器，获得永久加成'
    default: return '远征行程筹备中'
  }
}
function open(panel: string) {
  if (['tower', 'expedition'].includes(panel) && activeRun.value) { emit('resumeRun'); return }
  focusedDiscipleId.value = ''
  preparationReturn.value = null
  openPanel.value = panel
}
const nextAction = ref<NextAction | null>(null)
function held(id: string) {
  if (id === 'spirit_stone' || id === 'cultivation' || id === 'reputation' || id === 'stamina') return store.resources?.[id] ?? 0
  return store.state?.inventory[id] ?? 0
}
watch(() => store.lastSettle, async settle => {
  if (!settle) { nextAction.value = null; return }
  const [facilities, recipes] = await Promise.all([store.previewFacilities(), store.previewRecipes(1)])
  nextAction.value = pickNextAction(facilities?.facilities ?? [], recipes?.recipes ?? [], held, id => resourceName(id, catalog.value))
}, { immediate: true })
function openBuilding(id: string) {
  const spot = city.value?.hotspots.find(spot => spot.id === id)
  if (spot) open(spot.panel)
}
function openDisciple(id: string) {
  if (!store.disciples.some(disciple => disciple.id === id)) return
  open('codex')
  focusedDiscipleId.value = id
}
watch(() => store.slotId, () => { openPanel.value = null; focusedDiscipleId.value = ''; preparationReturn.value = null })
function editPreparation(panel:'tower'|'expedition') {
  preparationReturn.value = panel
  openPanel.value = 'codex'
}
function returnToPreparation() {
  openPanel.value = preparationReturn.value
  preparationReturn.value = null
}
function followGoal() {
  if (activeRun.value) { emit('resumeRun'); return }
  if (!store.disciples.length) { open('codex'); return }
  if (store.state?.last_run_review && !store.state.last_run_review.victory) { open('sect'); return }
  if (!store.state?.duty_slots.length) { open('duty'); return }
  const total = catalog.value?.mode.node_count ?? 0
  open(total && (store.state?.tower_floor ?? 0) >= total ? 'codex' : 'tower')
}
</script>
<template>
  <div class="city-page">
    <section class="city-scene" aria-label="宗门主城">
      <CityScene :key="store.slotId ?? 0" :actors="actors" :buildings="buildings" :lighting="lighting" @building="openBuilding" @disciple="openDisciple" />
      <div class="scene-heading"><span class="eyebrow">云岫仙宗 · 山居</span><h2>一山云水，满庭仙缘。</h2><p>{{ activeRun ? runLocation : `门下 ${store.disciples.length} 位同道 · 值守 ${store.state?.duty_slots.length ?? 0} 人` }}</p></div>
      <label class="sky-control"><span>{{ phaseName }}</span><select v-model="selection" aria-label="主城天色"><option value="auto">随时间</option><option v-for="phase in phases" :key="phase.id" :value="phase.id">{{ phase.name }}</option></select></label>
      <div class="scene-actions">
        <button class="goal-slip" @click="followGoal"><span class="goal-mark">令</span><span><small>当前修行</small><strong>{{ currentGoal }}</strong></span><span aria-hidden="true">›</span></button>
        <div class="collect-wrap">
          <button v-if="nextAction" class="next-slip" @click="open(nextAction.panel)">{{ nextAction.label }}<span aria-hidden="true">›</span></button>
          <button class="collect-button" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" /><span>收取收益<small>山中修行，自有所得</small></span></button>
        </div>
      </div>
      <span class="map-help">点击殿阁或同道 · 拖动游览，滚轮或双指缩放</span>
    </section>
    <CityDock :tower-label="towerLabel" :tower-hint="towerHint" :expedition-label="expeditionLabel" :expedition-hint="expeditionHint" :disciple-count="store.disciples.length" :duty-count="store.state?.duty_slots.length ?? 0" :active="openPanel" @open="open" />
    <PanelModal v-if="openPanel" :title="TITLES[openPanel] ?? '宗门事务'" :wide="['codex','tower','expedition','sect'].includes(openPanel)" @close="openPanel = null"><div v-if="activeRun && ['codex','duty','alchemy','forge'].includes(openPanel)" class="notice-box" style="margin-bottom:18px">出征尚未结算，可查阅宗门资料；阵容、弟子修炼、值守与炼制将在结算后恢复调整。</div><button v-if="openPanel==='codex' && preparationReturn" class="btn btn-small" style="margin-bottom:16px" @click="returnToPreparation">阵容已安排 · 返回{{ preparationReturn==='expedition'?'征讨整备':'问道准备' }}</button><CodexPanel v-if="openPanel === 'codex'" :read-only="!!activeRun" :initial-disciple-id="focusedDiscipleId" /><SectPanel v-else-if="openPanel === 'sect'" @open="open" /><DutyPanel v-else-if="openPanel === 'duty'" :read-only="!!activeRun" @open="open" /><CraftPanel v-else-if="openPanel === 'alchemy'" kind="pill" :read-only="!!activeRun" @open="open" /><CraftPanel v-else-if="openPanel === 'forge'" kind="artifact" :read-only="!!activeRun" @open="open" /><PreparePanel v-else-if="openPanel === 'tower'" @edit="editPreparation('tower')" /><ExpeditionPanel v-else-if="openPanel === 'expedition'" @edit="editPreparation('expedition')" /><div v-else class="empty-state"><strong>远行之路，尚待开启</strong>先经营宗门，在问道塔中磨砺弟子。</div></PanelModal>
  </div>
</template>
<style scoped>
.city-page{height:100%;min-height:0;display:flex;flex-direction:column;overflow:hidden;background:#cbd8bc}.city-scene{position:relative;flex:1;min-height:0;isolation:isolate;container-type:size}.scene-heading{position:absolute;z-index:2;left:30px;top:22px;pointer-events:none;text-shadow:0 1px #fcf6df}.scene-heading .eyebrow{color:#6f794f;font-size:10px}.scene-heading h2{margin:4px 0;font-size:22px;letter-spacing:.12em;color:#36573e}.scene-heading p{margin:0;font-size:11px;color:#5a7152}.sky-control{position:absolute;right:26px;top:22px;z-index:3;display:flex;align-items:center;gap:10px;padding:4px 7px 4px 12px;background:#f8f2dfd9;border:1px solid #bac0a3;color:#4c674e;font-size:12px;box-shadow:0 3px 10px #37543d11}.sky-control select{min-height:34px;padding:4px 22px 4px 8px;border:0;background:transparent;font-size:11px}.scene-actions{position:absolute;z-index:3;bottom:36px;left:30px;right:30px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;pointer-events:none}.scene-actions>button{pointer-events:auto;min-height:54px}.goal-slip{display:flex;align-items:center;gap:12px;max-width:calc(100% - 180px);padding:8px 14px 8px 9px;border:1px solid #b8a475;border-left:3px solid #8b7042;background:#faf1dcf0;color:#38563d;box-shadow:0 3px 0 #7b68452b,0 6px 18px #344a3422;text-align:left}.goal-slip:hover{background:#fff9e9}.goal-mark{display:grid;place-items:center;width:29px;height:33px;border:1px solid #b7a679;box-shadow:inset 0 0 0 2px #faf1dc;font:20px 'SimSun',serif;color:#8c713e;flex:none}.goal-slip small{display:block;font-size:9px;color:#8a805e;letter-spacing:.14em}.goal-slip strong{display:block;font-size:12px;font-weight:500}.goal-slip>span:last-child{font-size:24px;color:#a09267}.collect-button{display:flex;align-items:center;gap:10px;padding:10px 18px;border:1px solid #b99b5f;background:#345b46;color:#fff0c7;box-shadow:inset 0 0 0 3px #ffffff08,0 3px 0 #253f32,0 6px 20px #25413133;font:600 16px 'SimSun',serif}.collect-button:hover:not(:disabled){background:#294b38}.collect-wrap{display:flex;flex-direction:column;align-items:flex-end;gap:8px;pointer-events:none}.collect-wrap>button{pointer-events:auto}.collect-wrap .collect-button{min-height:54px}.next-slip{display:flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid #b8a475;background:#faf1dcf0;color:#38563d;font-size:11px;box-shadow:0 2px 0 #7b68452b}.next-slip:hover{background:#fff9e9}.next-slip>span{font-size:16px;color:#a09267}.collect-button .game-icon{width:26px;height:26px;color:#e0c57e}.collect-button small{display:block;font:9px/1.5 system-ui;color:#c6cfb2;margin-top:3px}.map-help{position:absolute;bottom:10px;left:0;right:0;text-align:center;font-size:9px;letter-spacing:.1em;color:#4d684d;pointer-events:none}
@media(max-width:640px){.scene-heading{left:12px;top:14px;padding:7px 10px;background:#faf3dfcf;border-left:2px solid #a89562;max-width:calc(100% - 112px)}.scene-heading .eyebrow{font-size:9px}.scene-heading h2{font-size:16px;letter-spacing:.03em}.scene-heading p{font-size:10px;max-width:210px}.sky-control{right:12px;top:14px;padding:2px 3px;font-size:10px}.sky-control>span{display:none}.sky-control select{min-height:40px;font-size:10px;padding-left:5px}.scene-actions{left:12px;right:12px;bottom:30px;gap:8px}.goal-slip{max-width:calc(100% - 112px);gap:7px;padding:7px}.goal-slip strong{font-size:11px}.goal-mark{width:23px;height:29px;font-size:17px}.goal-slip>span:last-child{display:none}.collect-button{gap:5px;padding:10px;font-size:14px}.collect-button .game-icon{width:18px;height:18px}.collect-button small{font-size:8px}}
@media(max-height:600px) and (min-width:641px){.scene-heading{top:10px;left:18px}.scene-heading h2{font-size:16px}.scene-heading p{display:none}.scene-actions{bottom:24px;left:18px;right:18px}.scene-actions>button{min-height:44px}.sky-control{top:10px}}
</style>
