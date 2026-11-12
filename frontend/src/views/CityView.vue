<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import CityDock from '../components/game/CityDock.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { sceneImage } from '../presentation/assetPaths'
import { effectText, type DisplayCatalog } from '../presentation/gameText'
import CityAtmosphere from '../rendering/CityAtmosphere.vue'
import { phases, useDayCycle } from '../rendering/dayCycle'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import CodexPanel from './CodexPanel.vue'
import CraftPanel from './CraftPanel.vue'
import DutyPanel from './DutyPanel.vue'
import SectPanel from './SectPanel.vue'
import PreparePanel from './PreparePanel.vue'
const emit = defineEmits<{ resumeRun: [] }>()
const store = useGameStore()
const { selection, phaseName, sceneStyle } = useDayCycle()
const openPanel = ref<string | null>(null)
const viewport = ref<HTMLDivElement | null>(null)
onMounted(() => { if (viewport.value) viewport.value.scrollLeft = (viewport.value.scrollWidth - viewport.value.clientWidth) / 2 })
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const city = computed(() => catalog.value?.city)
const cityBackground = computed(() => sceneImage(city.value?.background))
const activeRun = computed(() => store.state?.active_run ?? null)
const runEnded = computed(() => store.status === 'cleared' || store.status === 'defeated')
const runStep = computed(() => (activeRun.value?.nodes.length ?? 0) + (runEnded.value || store.status === 'choosing_affix' ? 0 : 1))
const towerLabel = computed(() => activeRun.value ? runEnded.value ? '待结算' : '继续出征' : '问道')
const towerHint = computed(() => activeRun.value ? `第 ${runStep.value} 层 · ${runEnded.value ? '收取战利品' : '试炼未歇'}` : '登塔试炼')
const runLocation = computed(() => runEnded.value ? `此次到达 ${runStep.value} 层，尚待结算` : store.status === 'choosing_affix' ? `第 ${activeRun.value?.nodes.length ?? 0} 层获胜，等待领悟道法` : `第 ${runStep.value} 层，等待选择路线`)
const TITLES: Record<string,string> = { codex:'门下弟子', sect:'宗门主殿', expedition:'远行码头', duty:'值守编制', forge:'炼器炉', alchemy:'炼丹房', tower:'问道塔 · 出征准备' }
const injured = computed(() => store.disciples.filter(d => d.injury_stacks > 0).length)
const recruitable = computed(() => Object.entries(catalog.value?.disciples ?? {}).filter(([id,d]) => !(store.state?.unlocks ?? []).includes(id) && (store.resources?.reputation ?? 0) >= (d.unlock_cost?.reputation??0)).length)
function craftable(kind: string) { return Object.values(catalog.value?.recipes ?? {}).filter(r => r.kind === kind && Object.entries(r.inputs).every(([id,n]) => (store.state?.inventory?.[id] ?? 0) >= n)).length }
const currentGoal = computed(() => {
  if (activeRun.value) return runEnded.value ? '收取此次出征战利品' : '继续问道塔试炼'
  if (!store.disciples.length) return '招募首位门下弟子'
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
    case 'tower': return activeRun.value ? `${runEnded.value ? '待结算' : '继续出征'} · 第 ${runStep.value} 层` : `最高记录 ${store.state?.tower_floor ?? 0} 层`
    case 'alchemy': return `伤员 ${injured.value} 人 · 可炼 ${craftable('pill')} 方`
    case 'forge': return `${Object.values(catalog.value?.recipes ?? {}).filter(recipe => recipe.kind === 'artifact').length} 种器方 · 可炼 ${craftable('artifact')} 方`
    default: return '尚未开放'
  }
}
function secondaryStatusOf(panel: string) {
  switch(panel) {
    case 'sect': return store.lastSettle && store.lastSettle.elapsed_hours >= .05 ? `离线收益已收取 ${number(store.lastSettle.elapsed_hours,1)} 小时 · 存档管理` : '离线收益 · 存档管理'
    case 'codex': return recruitable.value ? `${recruitable.value} 位贤才可招募` : '查看道法与同道羁绊'
    case 'duty': return `修为 +${number(store.production.cultivation,1)}/时 · 灵石 +${number(store.production.spirit_stone,1)}/时`
    case 'tower': return activeRun.value ? `最高记录 ${store.state?.tower_floor ?? 0} 层 · 队伍已锁定` : `${catalog.value?.mode.node_count ?? 0} 层试炼 · 行动力 ${catalog.value?.mode.stamina_cost ?? 1}`
    case 'alchemy': return '疗伤丹药 · 永久增益'
    case 'forge': return permanentBonuses.value.length ? `永久 ${permanentBonuses.value.slice(0,2).join(' · ')}` : '炼制法器，获得永久加成'
    default: return '远征行程筹备中'
  }
}
function open(panel: string) {
  if (panel === 'tower' && activeRun.value) { emit('resumeRun'); return }
  openPanel.value = panel
}
function followGoal() {
  if (activeRun.value) { emit('resumeRun'); return }
  if (!store.disciples.length) { open('codex'); return }
  if (!store.state?.duty_slots.length) { open('duty'); return }
  const total = catalog.value?.mode.node_count ?? 0
  open(total && (store.state?.tower_floor ?? 0) >= total ? 'codex' : 'tower')
}
function hideBroken(event: Event) { (event.target as HTMLImageElement).style.visibility = 'hidden' }
</script>
<template>
  <div class="city-page" :style="sceneStyle">
    <section class="city-scene" aria-label="宗门主城" :style="{ '--map-aspect': city?.aspect ?? 1.5 }">
      <div v-if="city" class="scene-extension" :style="{ backgroundImage: `url(${cityBackground})` }" aria-hidden="true"></div>
      <div ref="viewport" class="city-viewport" tabindex="0" aria-label="宗门地图，手机可左右滑动查看殿阁">
        <div v-if="city" class="city-map" :style="{ aspectRatio: String(city.aspect) }">
          <img :src="cityBackground" alt="云海之上的宗门，石径通向各座殿阁" class="city-background pixel-art" draggable="false" />
          <CityAtmosphere />
          <button v-for="spot in city.hotspots" :key="spot.id" class="building-hotspot" :class="{ 'is-tower': spot.panel === 'tower' }" :style="{ left:`${spot.x}%`,top:`${spot.y}%`,width:`${spot.w}%`,height:`${spot.h}%`,zIndex: Math.round(spot.y) }" :aria-label="`${spot.name}，${statusOf(spot.panel)}`" :title="`${statusOf(spot.panel)} · ${secondaryStatusOf(spot.panel)}`" @click="open(spot.panel)">
            <img v-if="spot.sprite" :src="sceneImage(spot.sprite)" alt="" class="building-sprite pixel-art" draggable="false" @error="hideBroken" />
            <span class="building-label"><strong>{{ spot.name }}</strong><small v-if="spot.panel === 'tower'">{{ activeRun ? towerLabel : `最高 ${store.state?.tower_floor ?? 0} 层` }}</small><small v-else-if="spot.panel === 'expedition'">尚未开放</small></span>
          </button>
        </div>
      </div>
      <div class="scene-heading"><span class="eyebrow">云岫仙宗 · 山居</span><h2>一山云水，满庭仙缘。</h2><p>{{ activeRun ? runLocation : `门下 ${store.disciples.length} 位同道 · 值守 ${store.state?.duty_slots.length ?? 0} 人` }}</p></div>
      <label class="sky-control"><span>{{ phaseName }}</span><select v-model="selection" aria-label="主城天色"><option value="auto">随时间</option><option v-for="phase in phases" :key="phase.id" :value="phase.id">{{ phase.name }}</option></select></label>
      <div class="scene-actions">
        <button class="goal-slip" @click="followGoal"><span class="goal-mark">令</span><span><small>当前修行</small><strong>{{ currentGoal }}</strong></span><span aria-hidden="true">›</span></button>
        <button class="collect-button" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" /><span>收取收益<small>山中修行，自有所得</small></span></button>
      </div>
      <span class="map-help">点击殿阁打理宗门<span> · 左右滑动游览</span></span>
    </section>
    <CityDock :tower-label="towerLabel" :tower-hint="towerHint" :disciple-count="store.disciples.length" :duty-count="store.state?.duty_slots.length ?? 0" :active="openPanel" @open="open" />
    <PanelModal v-if="openPanel" :title="TITLES[openPanel] ?? '宗门事务'" :wide="openPanel === 'codex' || openPanel === 'tower'" @close="openPanel = null"><div v-if="activeRun && ['codex','duty','alchemy','forge'].includes(openPanel)" class="notice-box" style="margin-bottom:18px">出征尚未结算，可查阅宗门资料；阵容、弟子修炼、值守与炼制将在结算后恢复调整。</div><CodexPanel v-if="openPanel === 'codex'" :read-only="!!activeRun" /><SectPanel v-else-if="openPanel === 'sect'" /><DutyPanel v-else-if="openPanel === 'duty'" :read-only="!!activeRun" /><CraftPanel v-else-if="openPanel === 'alchemy'" kind="pill" :read-only="!!activeRun" /><CraftPanel v-else-if="openPanel === 'forge'" kind="artifact" :read-only="!!activeRun" /><PreparePanel v-else-if="openPanel === 'tower'" @edit="openPanel = 'codex'" /><div v-else class="empty-state"><strong>远行之路，尚待开启</strong>先经营宗门，在问道塔中磨砺弟子。</div></PanelModal>
  </div>
</template>
<style scoped>
.city-page{height:100%;min-height:0;display:flex;flex-direction:column;overflow:hidden;background:#cbd8bc}.city-scene{position:relative;flex:1;min-height:0;isolation:isolate;container-type:size}.scene-extension{position:absolute;inset:-30px;background-position:center;background-size:cover;filter:blur(24px) brightness(var(--day-brightness,1)) saturate(var(--day-saturation,1));opacity:.7;pointer-events:none}.scene-extension::after{content:'';position:absolute;inset:0;background:#183561;mix-blend-mode:color;opacity:var(--night-opacity,0)}.city-viewport{position:absolute;z-index:1;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden}.city-map{position:relative;flex:none;width:min(100cqw,calc(100cqh * var(--map-aspect)));overflow:hidden}.city-background{display:block;width:100%;height:100%;filter:brightness(var(--day-brightness,1)) saturate(var(--day-saturation,1));transition:filter 3s ease}.city-map{mask-image:linear-gradient(90deg,transparent,#000 2%,#000 98%,transparent)}.building-hotspot{position:absolute;transform:translate(-50%,-50%);padding:0;border:0;background:transparent;overflow:visible}.building-hotspot:focus-visible{outline-offset:-4px}.building-sprite{width:100%;height:100%;object-fit:contain;object-position:center bottom;pointer-events:none;filter:drop-shadow(3px 5px 2px #16362d33);transition:filter .2s}.building-hotspot:hover .building-sprite,.building-hotspot:focus-visible .building-sprite{filter:brightness(1.13) drop-shadow(0 0 7px #f3e9a8b0)}.building-label{position:absolute;bottom:0;left:50%;transform:translateX(-50%);padding:3px 13px;min-width:76px;border:1px solid #aa986a;background:#faf1ddec;box-shadow:0 2px #76643a44,0 4px 12px #1c382422;white-space:nowrap;color:#304e3d;pointer-events:none}.building-label::before,.building-label::after{content:'';position:absolute;top:3px;bottom:3px;width:2px;background:#c0ad7d}.building-label::before{left:3px}.building-label::after{right:3px}.building-label strong{display:block;font:600 13px/1.5 'SimSun',serif;letter-spacing:.12em}.building-label small{display:block;font-size:9px;line-height:1.4;color:#7a7c60}.is-tower .building-label{background:#2b5447f2;border-color:#d4bd7f;color:#fff1c9}.is-tower small{color:#e3d7ae}.scene-heading{position:absolute;z-index:2;left:30px;top:22px;pointer-events:none;text-shadow:0 1px #fcf6df}.scene-heading .eyebrow{color:#6f794f;font-size:10px}.scene-heading h2{margin:4px 0;font-size:22px;letter-spacing:.12em;color:#36573e}.scene-heading p{margin:0;font-size:11px;color:#5a7152}.sky-control{position:absolute;right:26px;top:22px;z-index:3;display:flex;align-items:center;gap:10px;padding:4px 7px 4px 12px;background:#f8f2dfd9;border:1px solid #bac0a3;color:#4c674e;font-size:12px;box-shadow:0 3px 10px #37543d11}.sky-control select{min-height:34px;padding:4px 22px 4px 8px;border:0;background:transparent;font-size:11px}.scene-actions{position:absolute;z-index:3;bottom:36px;left:30px;right:30px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;pointer-events:none}.scene-actions>button{pointer-events:auto;min-height:54px}.goal-slip{display:flex;align-items:center;gap:12px;max-width:calc(100% - 180px);padding:8px 14px 8px 9px;border:1px solid #b8a475;border-left:3px solid #8b7042;background:#faf1dcf0;color:#38563d;box-shadow:0 3px 0 #7b68452b,0 6px 18px #344a3422;text-align:left}.goal-slip:hover{background:#fff9e9}.goal-mark{display:grid;place-items:center;width:29px;height:33px;border:1px solid #b7a679;box-shadow:inset 0 0 0 2px #faf1dc;font:20px 'SimSun',serif;color:#8c713e;flex:none}.goal-slip small{display:block;font-size:9px;color:#8a805e;letter-spacing:.14em}.goal-slip strong{display:block;font-size:12px;font-weight:500}.goal-slip>span:last-child{font-size:24px;color:#a09267}.collect-button{display:flex;align-items:center;gap:10px;padding:10px 18px;border:1px solid #b99b5f;background:#345b46;color:#fff0c7;box-shadow:inset 0 0 0 3px #ffffff08,0 3px 0 #253f32,0 6px 20px #25413133;font:600 16px 'SimSun',serif}.collect-button:hover:not(:disabled){background:#294b38}.collect-button .game-icon{width:26px;height:26px;color:#e0c57e}.collect-button small{display:block;font:9px/1.5 system-ui;color:#c6cfb2;margin-top:3px}.map-help{position:absolute;bottom:10px;left:0;right:0;text-align:center;font-size:9px;letter-spacing:.1em;color:#4d684d;pointer-events:none}.map-help>span{display:none}
@media(max-width:640px){.city-viewport{justify-content:flex-start;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:none}.city-map{width:max(100cqw,calc(100cqh * var(--map-aspect)));margin:auto;mask-image:none}.scene-heading{left:12px;top:14px;padding:7px 10px;background:#faf3dfcf;border-left:2px solid #a89562;max-width:calc(100% - 112px)}.scene-heading .eyebrow{font-size:9px}.scene-heading h2{font-size:16px;letter-spacing:.03em}.scene-heading p{font-size:10px;max-width:210px}.sky-control{right:12px;top:14px;padding:2px 3px;font-size:10px}.sky-control>span{display:none}.sky-control select{min-height:40px;font-size:10px;padding-left:5px}.scene-actions{left:12px;right:12px;bottom:30px;gap:8px}.goal-slip{max-width:calc(100% - 112px);gap:7px;padding:7px}.goal-slip strong{font-size:11px}.goal-mark{width:23px;height:29px;font-size:17px}.goal-slip>span:last-child{display:none}.collect-button{gap:5px;padding:10px;font-size:14px}.collect-button .game-icon{width:18px;height:18px}.collect-button small{font-size:8px}.map-help>span{display:inline}.building-label{padding:3px 10px;min-width:70px}.building-label strong{font-size:12px}}
@media(max-height:600px) and (min-width:641px){.scene-heading{top:10px;left:18px}.scene-heading h2{font-size:16px}.scene-heading p{display:none}.scene-actions{bottom:24px;left:18px;right:18px}.scene-actions>button{min-height:44px}.sky-control{top:10px}}
</style>
