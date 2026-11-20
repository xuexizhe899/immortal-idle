<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CityDock from '../components/game/CityDock.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { discipleImage } from '../presentation/assetPaths'
import { resourceName, type DisplayCatalog } from '../presentation/gameText'
import { pickNextAction, type NextAction } from '../presentation/nextAction'
import CityScene from '../rendering/hd2d/CityScene.vue'
import { projectCityActors } from '../rendering/hd2d/cityModel'
import { phases, useDayCycle } from '../rendering/dayCycle'
import { durationFromHours, number } from '../shared/format'
import { useGameStore } from '../stores/game'
import CodexPanel from './CodexPanel.vue'
import CraftPanel from './CraftPanel.vue'
import DutyPanel from './DutyPanel.vue'
import SectPanel from './SectPanel.vue'
import PreparePanel from './PreparePanel.vue'
import WorldPanel from './WorldPanel.vue'
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
const runUnit = computed(() => activeRun.value?.mode === 'tower' ? '层' : activeRun.value?.mode === 'expedition' ? '段' : '关')
const runName = computed(() => String((activeRun.value?.party_snapshot?.mode.world_node as Record<string, unknown> | undefined)?.name ?? (activeRun.value?.mode === 'tower' ? '问道塔试炼' : activeRun.value?.mode === 'dungeon' ? '秘境历练' : '山河历练')))
const currentTowerBest = computed(() => Math.max((store.state?.world.current_region ?? 1) === 1 ? store.state?.tower_floor ?? 0 : 0, ...Object.values(store.state?.tower_tiers ?? {})))
const towerLabel = computed(() => activeRun.value?.mode === 'tower' ? runEnded.value ? '待结算' : '继续出征' : '问道')
const towerHint = computed(() => activeRun.value?.sect_id ? '征讨中 · 点击继续' : activeRun.value ? `${runName.value} · 第 ${runStep.value} ${runUnit.value} · ${runEnded.value ? '收取战利品' : '点击继续'}` : '登塔试炼')
const expeditionLabel = computed(() => activeRun.value && activeRun.value.mode !== 'tower' ? (runEnded.value ? '待结算' : '继续出征') : '山河')
const expeditionHint = computed(() => activeRun.value?.sect_id ? (activeRun.value.is_retrial ? '论道中 · 点击继续' : `守备 ${activeRun.value.guard} · ${runEnded.value ? '等待结算' : '宗门征讨中'}`) : activeRun.value ? '出征中 · 点击继续' : `已攻克 ${store.state?.sects.filter(sect=>sect.conquered).length ?? 0} / ${store.state?.sects.length ?? 0} 座宗门`)
const runLocation = computed(() => activeRun.value?.sect_id ? `${activeRun.value.is_retrial ? '论道' : '宗门征讨'} · ${runEnded.value ? '等待结算' : activeRun.value.guard===0 ? '等待挑战宗主' : '守备 '+activeRun.value.guard+' · 等待安排上阵'}` : `${runName.value} · ${runEnded.value ? `此次到达 ${runStep.value} ${runUnit.value}，尚待结算` : store.status === 'choosing_affix' ? `第 ${activeRun.value?.nodes.length ?? 0} ${runUnit.value}获胜，等待领悟道法` : `第 ${runStep.value} ${runUnit.value}，等待选择路线`}`)
const TITLES: Record<string,string> = { codex:'弟子堂', sect:'宗门主殿', expedition:'山河地图', duty:'值守编制', forge:'炼器阁', alchemy:'炼丹房', tower:'问道塔 · 出征准备' }
const injured = computed(() => store.disciples.filter(d => d.injury_stacks > 0).length)
const recruitable = computed(() => Object.entries(catalog.value?.disciples ?? {}).filter(([id,d]) => !(store.state?.unlocks ?? []).includes(id) && (store.resources?.reputation ?? 0) >= (d.unlock_cost?.reputation??0)).length)
const currentGoal = computed(() => {
  if (activeRun.value) return runEnded.value ? '收取此次出征战利品' : activeRun.value.world_node_id ? '继续山河历练' : activeRun.value.mode === 'expedition' ? '继续宗门征讨' : '继续问道塔试炼'
  if (!store.disciples.length) return '招募首位门下弟子'
  if (store.state?.last_run_review && !store.state.last_run_review.victory) return '复盘上次出征，调整队伍'
  if (!store.state?.duty_slots.length) return '安排弟子值守'
  if (!Object.keys(store.state.gear ?? {}).length) return '探索秘境，获取个人装备'
  const region = store.state.world.current_region
  if (!store.state.world.cleared_nodes.includes(`r${region}:invasion:3`)) return '推进片区守关，迎击关键入侵'
  return region === 1 ? '使用升仙令，飞升青冥灵域' : '修炼配装，挑战新境山河'
})
function statusOf(panel: string) {
  switch(panel) {
    case 'sect': return currentGoal.value
    case 'codex': return `弟子 / 招贤 · 门下 ${store.disciples.length} 人`
    case 'duty': return `值守 ${store.state?.duty_slots.length ?? 0} / ${catalog.value?.rules.max_duty ?? 6}`
    case 'tower': return activeRun.value ? `${runEnded.value ? '待结算' : '继续出征'} · 第 ${runStep.value} ${runUnit.value}` : `本地区最高记录 ${currentTowerBest.value} 层`
    case 'expedition': return expeditionHint.value
    case 'alchemy': return `伤员 ${injured.value} 人 · 炼丹房 ${store.state?.facility_levels.alchemy ?? 1} 级`
    case 'forge': return `炼器阁 ${store.state?.facility_levels.forge ?? 1} 级 · 四槽装备与专武培养`
    default: return '尚未开放'
  }
}
function secondaryStatusOf(panel: string) {
  switch(panel) {
    case 'sect': return store.state?.idle_record ? `累计有效时长 ${durationFromHours(store.state.idle_record.elapsed_hours)} · 已自动入账` : '设施升级 · 挂机记录 · 存档管理'
    case 'codex': return recruitable.value ? `${recruitable.value} 位贤才可招募` : '查看道法与同道羁绊'
    case 'duty': return `修为 +${number(store.production.cultivation,1)}/时 · 灵石 +${number(store.production.spirit_stone,1)}/时`
    case 'tower': return activeRun.value ? `本地区最高记录 ${currentTowerBest.value} 层 · 队伍已锁定` : `${catalog.value?.mode.node_count ?? 0} 层试炼 · 行动力 ${catalog.value?.mode.stamina_cost ?? 1}`
    case 'expedition': return activeRun.value ? '当前已有出征，先完成或结算后再启程' : '秘境寻器 · 攻宗驻守 · 迎击飞升'
    case 'alchemy': return '疗伤丹药 · 永久增益'
    case 'forge': return '个人装备强化 · 洗练 · 熔炼 · 专武锻造'
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
  open('expedition')
}
</script>
<template>
  <div class="city-page">
    <section class="city-scene" aria-label="宗门主城">
      <CityScene :key="store.slotId ?? 0" :actors="actors" :buildings="buildings" :lighting="lighting" @building="openBuilding" @disciple="openDisciple" />
      <div class="scene-heading"><span class="eyebrow">云岫仙宗 · 山居</span><h2>一山云水，满庭仙缘。</h2><p>{{ activeRun ? runLocation : `门下 ${store.disciples.length} 位同道 · 值守 ${store.state?.duty_slots.length ?? 0} 人` }}<span v-if="injured" class="scene-injury">{{ injured }} 位有伤</span></p></div>
      <label class="sky-control" :data-phase="lighting.phase" title="预览主城天色，不影响修行收益"><i class="phase-orb" aria-hidden="true"></i><span>{{ phaseName }}</span><select v-model="selection" aria-label="主城天色"><option value="auto">随时间</option><option v-for="phase in phases" :key="phase.id" :value="phase.id">{{ phase.name }}</option></select></label>
      <div class="scene-actions">
        <button class="goal-slip" :class="{ travelling: !!activeRun, ended: runEnded }" @click="followGoal"><span class="goal-mark">令</span><span><small>{{ activeRun ? runEnded ? '战利品待结算' : '同道历练中' : '当前修行' }}</small><strong>{{ currentGoal }}</strong></span><span aria-hidden="true">›</span></button>
        <div class="collect-wrap">
          <button v-if="nextAction" class="next-slip" @click="open(nextAction.panel)">{{ nextAction.label }}<span aria-hidden="true">›</span></button>
          <button class="collect-button" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" /><span>同步挂机收益<small>后台记录，收益自动入账</small></span></button>
        </div>
      </div>
      <span class="map-help">点击殿阁或同道 · 拖动游览，滚轮或双指缩放</span>
    </section>
    <CityDock :tower-label="towerLabel" :tower-hint="towerHint" :expedition-label="expeditionLabel" :expedition-hint="expeditionHint" :disciple-count="store.disciples.length" :duty-count="store.state?.duty_slots.length ?? 0" :active="openPanel" @open="open" />
    <PanelModal v-if="openPanel" :title="TITLES[openPanel] ?? '宗门事务'" :wide="['codex','tower','expedition','sect'].includes(openPanel)" @close="openPanel = null"><div v-if="activeRun && ['codex','duty','alchemy','forge'].includes(openPanel)" class="notice-box" style="margin-bottom:18px">出征尚未结算，可查阅宗门资料；阵容、弟子修炼、值守与炼制将在结算后恢复调整。</div><button v-if="openPanel==='codex' && preparationReturn" class="btn btn-small" style="margin-bottom:16px" @click="returnToPreparation">阵容已安排 · 返回{{ preparationReturn==='expedition'?'征讨整备':'问道准备' }}</button><CodexPanel v-if="openPanel === 'codex'" :read-only="!!activeRun" :initial-disciple-id="focusedDiscipleId" /><SectPanel v-else-if="openPanel === 'sect'" @open="open" /><DutyPanel v-else-if="openPanel === 'duty'" :read-only="!!activeRun" @open="open" /><CraftPanel v-else-if="openPanel === 'alchemy'" kind="pill" :read-only="!!activeRun" @open="open" /><CraftPanel v-else-if="openPanel === 'forge'" kind="artifact" :read-only="!!activeRun" @open="open" /><PreparePanel v-else-if="openPanel === 'tower'" @edit="editPreparation('tower')" /><WorldPanel v-else-if="openPanel === 'expedition'" @edit="editPreparation('expedition')" /><div v-else class="empty-state"><strong>远行之路，尚待开启</strong>先经营宗门，在问道塔中磨砺弟子。</div></PanelModal>
  </div>
</template>
<style scoped>
.city-page{height:100%;min-height:0;display:flex;flex-direction:column;overflow:hidden;background:#cbd8bc}.city-scene{position:relative;flex:1;min-height:0;isolation:isolate;container-type:size}.scene-heading{position:absolute;z-index:2;left:30px;top:22px;pointer-events:none;text-shadow:0 1px #fcf6df}.scene-heading .eyebrow{color:#6f794f;font-size:10px}.scene-heading h2{margin:4px 0;font-size:22px;letter-spacing:.12em;color:#36573e}.scene-heading p{margin:0;font-size:11px;color:#5a7152}.sky-control{position:absolute;right:26px;top:22px;z-index:3;display:flex;align-items:center;gap:10px;padding:4px 7px 4px 12px;background:#f8f2dfd9;border:1px solid #bac0a3;color:#4c674e;font-size:12px;box-shadow:0 3px 10px #37543d11}.sky-control select{min-height:34px;padding:4px 22px 4px 8px;border:0;background:transparent;font-size:11px}.scene-actions{position:absolute;z-index:3;bottom:36px;left:30px;right:30px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;pointer-events:none}.scene-actions>button{pointer-events:auto;min-height:54px}.goal-slip{display:flex;align-items:center;gap:12px;max-width:calc(100% - 180px);padding:8px 14px 8px 9px;border:1px solid #b8a475;border-left:3px solid #8b7042;background:#faf1dcf0;color:#38563d;box-shadow:0 3px 0 #7b68452b,0 6px 18px #344a3422;text-align:left}.goal-slip:hover{background:#fff9e9}.goal-mark{display:grid;place-items:center;width:29px;height:33px;border:1px solid #b7a679;box-shadow:inset 0 0 0 2px #faf1dc;font:20px 'SimSun',serif;color:#8c713e;flex:none}.goal-slip small{display:block;font-size:9px;color:#8a805e;letter-spacing:.14em}.goal-slip strong{display:block;font-size:12px;font-weight:500}.goal-slip>span:last-child{font-size:24px;color:#a09267}.collect-button{display:flex;align-items:center;gap:10px;padding:10px 18px;border:1px solid #b99b5f;background:#345b46;color:#fff0c7;box-shadow:inset 0 0 0 3px #ffffff08,0 3px 0 #253f32,0 6px 20px #25413133;font:600 16px 'SimSun',serif}.collect-button:hover:not(:disabled){background:#294b38}.collect-wrap{display:flex;flex-direction:column;align-items:flex-end;gap:8px;pointer-events:none}.collect-wrap>button{pointer-events:auto}.collect-wrap .collect-button{min-height:54px}.next-slip{display:flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid #b8a475;background:#faf1dcf0;color:#38563d;font-size:11px;box-shadow:0 2px 0 #7b68452b}.next-slip:hover{background:#fff9e9}.next-slip>span{font-size:16px;color:#a09267}.collect-button .game-icon{width:26px;height:26px;color:#e0c57e}.collect-button small{display:block;font:9px/1.5 system-ui;color:#c6cfb2;margin-top:3px}.map-help{position:absolute;bottom:10px;left:0;right:0;text-align:center;font-size:9px;letter-spacing:.1em;color:#4d684d;pointer-events:none}
@media(max-width:640px){.scene-heading{left:12px;top:14px;padding:7px 10px;background:#faf3dfcf;border-left:2px solid #a89562;max-width:calc(100% - 112px)}.scene-heading .eyebrow{font-size:9px}.scene-heading h2{font-size:16px;letter-spacing:.03em}.scene-heading p{font-size:10px;max-width:210px}.sky-control{right:12px;top:14px;padding:2px 3px;font-size:10px}.sky-control>span{display:none}.sky-control select{min-height:40px;font-size:10px;padding-left:5px}.scene-actions{left:12px;right:12px;bottom:30px;gap:8px}.goal-slip{max-width:calc(100% - 112px);gap:7px;padding:7px}.goal-slip strong{font-size:11px}.goal-mark{width:23px;height:29px;font-size:17px}.goal-slip>span:last-child{display:none}.collect-button{gap:5px;padding:10px;font-size:14px}.collect-button .game-icon{width:18px;height:18px}.collect-button small{font-size:8px}}
@media(max-height:600px) and (min-width:641px){.scene-heading{top:10px;left:18px}.scene-heading h2{font-size:16px}.scene-heading p{display:none}.scene-actions{bottom:24px;left:18px;right:18px}.scene-actions>button{min-height:44px}.sky-control{top:10px}}
.scene-heading{max-width:min(440px,calc(100% - 215px));padding:12px 17px 11px;border:1px solid #c2bea1;border-left:3px solid #648064;background:#faf5e5ed;box-shadow:inset 0 0 0 3px #fff9e780,0 4px 16px #324b3420;text-shadow:none}.scene-heading h2{font-size:20px}.scene-heading p{line-height:1.65;overflow-wrap:anywhere}.scene-injury{display:inline-block;margin-left:8px;padding-inline:5px;color:#914e3c;background:#f1e4cf;border:1px solid #d4b995;font-size:10px;white-space:nowrap}
.sky-control{gap:8px;background:#faf5e5ed}.phase-orb{display:block;width:12px;height:12px;flex:none;border:1px solid #ad8b49;border-radius:50%;background:#e1bc6a;box-shadow:0 0 0 3px #e7d9b34a}.sky-control[data-phase="night"] .phase-orb{border-color:#798d86;background:#ecedd6;box-shadow:inset -4px -2px #5e7d76}.sky-control[data-phase="dusk"] .phase-orb{background:#c88b59;border-color:#ac7650}.sky-control[data-phase="dawn"] .phase-orb{background:#e9c99b;border-color:#b69a66}
.goal-slip{flex:1;min-width:0;max-width:390px;transition:background .15s,border-color .15s}.goal-slip>span:nth-child(2){min-width:0}.goal-slip.travelling{border-left-color:#326c55}.goal-slip.ended{border-left-color:#b38a46;background:#fff2ce}.goal-slip strong{line-height:1.6}.goal-slip:focus-visible,.collect-button:focus-visible,.next-slip:focus-visible{outline:2px solid #f9f1d5;outline-offset:3px;box-shadow:0 0 0 5px #326c55}.collect-wrap{flex:none}.collect-button{transition:background .15s,transform .15s,box-shadow .15s}.collect-button:active:not(:disabled){transform:translateY(2px);box-shadow:inset 0 2px 4px #122d2740}.collect-button:disabled{opacity:1;background:#65745d;color:#eee9d8;cursor:progress}.collect-button:disabled small{color:#e3e5d4}
@media(max-width:640px){.scene-heading{max-width:calc(100% - 112px);padding:8px 10px}.scene-heading h2{font-size:16px}.scene-injury{font-size:9px;margin-left:4px}.sky-control{gap:4px}.phase-orb{width:9px;height:9px;margin-left:4px;box-shadow:none}.goal-slip{max-width:none}.collect-button{font-size:13px}.map-help{letter-spacing:.02em}}
@media(max-height:600px) and (min-width:641px){.scene-heading{padding:7px 12px}.scene-heading h2{font-size:16px}}
</style>
<style scoped>
/* 主城是空间首页：把控件压到边缘，给场景本身留出呼吸感。 */
.city-page {
  --scene-ink: #e8eddc;
  --scene-muted: #b4c4af;
  --scene-line: #a9c39d;
  background: #10251f;
}
.city-scene::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, #0b1e1a22 0%, transparent 30%, transparent 70%, #081b1688 100%);
  z-index: 1;
}
.scene-heading {
  left: 28px;
  top: 24px;
  max-width: min(480px, calc(100% - 220px));
  padding: 0 0 0 15px;
  border: 0;
  border-left: 2px solid var(--scene-line);
  background: transparent;
  box-shadow: none;
  color: var(--scene-ink);
  text-shadow: 0 2px 8px #071710aa;
}
.scene-heading .eyebrow {
  color: #d2bd7b;
  letter-spacing: .22em;
  font-size: 10px;
}
.scene-heading h2 {
  margin: 5px 0 2px;
  color: var(--scene-ink);
  font-size: clamp(20px, 2.2vw, 28px);
  letter-spacing: .12em;
  line-height: 1.35;
}
.scene-heading p { color: var(--scene-muted); font-size: 11px; }
.scene-injury { color: #f0c8a6; background: #542f2b99; border: 1px solid #bb755a; }
.sky-control {
  right: 28px;
  top: 24px;
  min-height: 38px;
  padding: 3px 5px 3px 12px;
  border: 1px solid #d2e0c044;
  background: #0e2923cc;
  box-shadow: 0 8px 24px #07171055;
  color: #d9e3d1;
  backdrop-filter: blur(8px);
}
.sky-control select { color: #d9e3d1; }
.sky-control select option { color: #20332b; background: #eff2e7; }
.phase-orb { box-shadow: 0 0 0 3px #a6c2991c; }
.scene-actions {
  left: 28px;
  right: 28px;
  bottom: 28px;
  align-items: flex-end;
}
.goal-slip {
  max-width: min(430px, calc(100% - 190px));
  min-height: 58px;
  padding: 9px 15px 9px 10px;
  border: 1px solid #ccdbbe55;
  border-left: 3px solid #c8b36e;
  background: #102c25dd;
  box-shadow: 0 10px 28px #06161055;
  color: #e9eedf;
  backdrop-filter: blur(8px);
}
.goal-slip:hover { background: #173a30ee; border-color: #d7e7c977; }
.goal-mark { border-color: #c8b36e99; box-shadow: inset 0 0 0 2px #102c25; color: #e0c783; }
.goal-slip small { color: #aabfa8; }
.goal-slip strong { color: #f0f2e5; }
.goal-slip > span:last-child { color: #bfcf9e; }
.goal-slip.travelling { border-left-color: #77b99a; }
.goal-slip.ended { border-left-color: #dbb86a; background: #3a3320dd; }
.next-slip {
  min-height: 36px;
  border: 1px solid #d8c17c66;
  background: #172f28e6;
  box-shadow: 0 6px 18px #06161055;
  color: #e2e9d9;
}
.next-slip:hover { background: #21463a; }
.collect-button {
  min-height: 58px;
  padding: 10px 18px;
  border: 1px solid #d9c37b;
  background: #d4b86b;
  color: #182d26;
  box-shadow: 0 6px 20px #06161066;
}
.collect-button:hover:not(:disabled) { background: #e1c980; }
.collect-button .game-icon { color: #284b3b; }
.collect-button small { color: #3d5b49; }
.collect-button:disabled { background: #71806d; color: #dfe7d8; }
.collect-button:disabled small { color: #d3ddcf; }
.map-help {
  bottom: 9px;
  color: #d1ddc9aa;
  letter-spacing: .12em;
  text-shadow: 0 1px 4px #06161099;
}
@media (max-width: 640px) {
  .scene-heading { left: 15px; top: 15px; max-width: calc(100% - 125px); padding-left: 10px; }
  .scene-heading .eyebrow { font-size: 8px; letter-spacing: .12em; }
  .scene-heading h2 { font-size: 17px; letter-spacing: .04em; }
  .scene-heading p { margin-top: 2px; color: #c0cfbd; }
  .sky-control { right: 12px; top: 15px; min-height: 36px; padding-left: 7px; }
  .scene-actions { left: 12px; right: 12px; bottom: 22px; gap: 8px; }
  .goal-slip { max-width: calc(100% - 106px); min-height: 52px; padding: 7px 9px; }
  .goal-slip strong { font-size: 11px; }
  .collect-button { min-height: 52px; padding: 8px 10px; font-size: 13px; }
  .collect-button small { font-size: 8px; }
  .next-slip { max-width: 170px; overflow: hidden; text-overflow: ellipsis; }
  .map-help { font-size: 8px; letter-spacing: .02em; }
}
</style>
