<script setup lang="ts">
import { computed, ref } from 'vue'
import GameIcon from '../components/GameIcon.vue'
import CityAtmosphere from '../components/CityAtmosphere.vue'
import { phases, useDayCycle } from '../components/dayCycle'
import PanelModal from '../components/PanelModal.vue'
import PartyStrip from '../components/PartyStrip.vue'
import { effectText, number, resourceName, type DisplayCatalog } from '../components/gameDisplay'
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
const showLastRun = ref(true)
const showSettle = ref(true)
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const city = computed(() => catalog.value?.city)
const activeRun = computed(() => store.state?.active_run ?? null)
const runEnded = computed(() => store.status === 'cleared' || store.status === 'defeated')
const runStep = computed(() => (activeRun.value?.nodes.length ?? 0) + (runEnded.value ? 0 : 1))
const resumeLabel = computed(() => runEnded.value ? '查看出征结算' : '继续出征')
const runLocation = computed(() => runEnded.value ? `此次到达 ${runStep.value} 层，尚待结算` : store.status === 'choosing_affix' ? `第 ${activeRun.value?.nodes.length ?? 0} 层获胜，等待领悟道法` : `第 ${runStep.value} 层，等待选择路线`)
const TITLES: Record<string,string> = { codex:'门下弟子', sect:'宗门主殿', expedition:'远行码头', duty:'值守编制', forge:'炼器炉', alchemy:'炼丹房', tower:'问道塔 · 出征准备' }
const NAV = [{id:'sect',name:'宗门',icon:'home'},{id:'codex',name:'弟子/招贤',icon:'people'},{id:'duty',name:'值守',icon:'sword'},{id:'alchemy',name:'炼丹',icon:'flame'},{id:'forge',name:'炼器',icon:'stone'},{id:'tower',name:'问道塔',icon:'tower'},{id:'expedition',name:'码头',icon:'bag'}]
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
function hideBroken(event: Event) { (event.target as HTMLImageElement).style.visibility = 'hidden' }
</script>
<template>
  <div class="city-page" :style="sceneStyle">
    <div class="city-topline"><div><span class="eyebrow">THE SECT IN THE CLOUDS</span><h2>云深不知处，仙山自有期。</h2></div><button class="btn btn-small" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" />收取挂机收益</button></div>
    <div class="environment-bar"><span><i></i>{{ phaseName }}<small>{{ selection === 'auto' ? '随山中时辰流转' : '天色预览' }}</small></span><label>天色<select v-model="selection" aria-label="主城天色"><option value="auto">随时间</option><option v-for="phase in phases" :key="phase.id" :value="phase.id">{{ phase.name }}</option></select></label></div>
    <div v-if="activeRun" class="notice-box" style="max-width:1100px;margin:0 auto 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap"><div><strong>问道塔出征仍在进行</strong><span style="display:block;font-size:11px">{{ runLocation }}。浏览宗门不会结束出征。</span></div><button class="btn btn-primary btn-small" :disabled="store.busy" @click="$emit('resumeRun')">{{ resumeLabel }}</button></div>
    <div class="city-viewport"><div v-if="city" class="city-map" :style="{ aspectRatio: String(city.aspect) }">
      <img :src="city.background" alt="云海之上的宗门，石径通向各座殿阁" class="city-background pixel-art" draggable="false" /><div class="map-vignette"></div>
      <CityAtmosphere />
      <button v-for="spot in city.hotspots" :key="spot.id" class="building-hotspot" :class="{ 'is-tower': spot.panel === 'tower' }" :style="{ left:`${spot.x}%`,top:`${spot.y}%`,width:`${spot.w}%`,height:`${spot.h}%`,zIndex: Math.round(spot.y) }" :aria-label="`${spot.name}，${statusOf(spot.panel)}`" @click="open(spot.panel)">
        <img v-if="spot.sprite" :src="spot.sprite" :alt="spot.name" class="building-sprite pixel-art" draggable="false" @error="hideBroken" /><span v-if="spot.anim === 'alchemy' || spot.anim === 'forge'" class="smoke" aria-hidden="true"><i></i><i></i><i></i></span><span class="building-label"><strong>{{ spot.name }}</strong><small>{{ statusOf(spot.panel) }}</small><small>{{ secondaryStatusOf(spot.panel) }}</small></span>
      </button>
      <div class="map-caption"><span class="map-compass">✧</span><span>云岫仙宗<small>点击殿阁，打理宗门事务</small></span></div>
    </div></div>
    <nav class="city-navigation" aria-label="宗门功能"><button v-for="item in NAV" :key="item.id" @click="open(item.id)"><GameIcon :name="item.icon" /><span>{{ item.name }}</span></button></nav>
    <div class="city-bottom"><div class="sect-status"><span><i></i>宗门安宁</span><span>值守 {{ store.state?.duty_slots?.length ?? 0 }} / 6</span><span v-if="injured" class="injury-note">{{ injured }} 位弟子有伤在身</span><span v-else>弟子状态良好</span><span class="tower-record">问道塔记录 <b>{{ store.state?.tower_floor ?? 0 }}</b> 层</span></div><PartyStrip @edit="open('codex')" @prepare="open('tower')" /></div>
    <div v-if="store.lastSettle && store.lastSettle.elapsed_hours>=0.05 && showSettle" class="last-run notice-box"><div><strong>离山期间，修行未歇</strong> · {{ number(store.lastSettle.elapsed_hours,1) }} 小时 <span>修为 +{{ number(store.lastSettle.gained.cultivation,1) }}</span><span>灵石 +{{ number(store.lastSettle.gained.spirit_stone,1) }}</span><span>行动力 +{{ number(store.lastSettle.gained.stamina,1) }}</span></div><button class="btn btn-small btn-quiet" aria-label="关闭挂机回报" @click="showSettle=false"><GameIcon name="close" /></button></div>
    <div v-if="store.lastRun && showLastRun" class="last-run notice-box"><div><strong>{{ store.lastRun.victory ? '问道功成' : '整顿再来' }}</strong> · 到达 {{ store.lastRun.cleared }} 层 <span v-for="(value,key) in store.lastRun.loot" :key="key">{{ resourceName(key, catalog) }} +{{ number(value,1) }}</span></div><button class="btn btn-small btn-quiet" aria-label="关闭出征回报" @click="showLastRun = false"><GameIcon name="close" /></button></div>
    <PanelModal v-if="openPanel" :title="TITLES[openPanel] ?? '宗门事务'" :wide="openPanel === 'codex' || openPanel === 'tower'" @close="openPanel = null"><div v-if="activeRun && ['codex','duty','alchemy','forge'].includes(openPanel)" class="notice-box" style="margin-bottom:18px">出征尚未结算，可查阅宗门资料；阵容、弟子修炼、值守与炼制将在结算后恢复调整。</div><CodexPanel v-if="openPanel === 'codex'" :read-only="!!activeRun" /><SectPanel v-else-if="openPanel === 'sect'" /><DutyPanel v-else-if="openPanel === 'duty'" :read-only="!!activeRun" /><CraftPanel v-else-if="openPanel === 'alchemy'" kind="pill" :read-only="!!activeRun" /><CraftPanel v-else-if="openPanel === 'forge'" kind="artifact" :read-only="!!activeRun" /><PreparePanel v-else-if="openPanel === 'tower'" @edit="openPanel = 'codex'" /><div v-else class="empty-state"><strong>远行之路，尚待开启</strong>先经营宗门，在问道塔中磨砺弟子。</div></PanelModal>
  </div>
</template>
<style scoped>
.city-page{position:relative;max-width:1800px;margin:0 auto;padding:24px 38px}.city-topline{display:flex;align-items:center;justify-content:space-between;gap:20px;max-width:1380px;margin:0 auto 12px}.city-topline h2{margin:3px 0;font-size:18px;letter-spacing:.15em}.city-topline .eyebrow{font-size:8px}.city-topline>.btn{background:#f9f4e3c9;font-size:11px}.city-viewport{display:flex;justify-content:center;overflow:hidden}.city-map{position:relative;width:100%;max-width:min(1200px,calc((100dvh - 320px) * 1.5));min-width:680px;overflow:visible;filter:drop-shadow(0 12px 20px #42533d25)}.city-background{display:block;width:100%;height:100%;object-fit:cover;mask-image:linear-gradient(to bottom,transparent 0%,#000 4%,#000 91%,transparent 100%)}.map-vignette{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at center,transparent 45%,#d4dec2aa 100%);mix-blend-mode:soft-light}.building-hotspot{position:absolute;transform:translate(-50%,-50%);padding:0;border:0;background:transparent;overflow:visible}.building-sprite{width:100%;height:100%;object-fit:contain;object-position:center bottom;pointer-events:none;transition:filter .2s ease;filter:drop-shadow(3px 5px 2px #16362d33)}.building-hotspot:hover .building-sprite,.building-hotspot:focus-visible .building-sprite{filter:brightness(1.1) drop-shadow(0 0 7px #f3e9a8b0)}.building-label{position:absolute;bottom:-19px;left:50%;transform:translateX(-50%);padding:5px 12px 4px;min-width:98px;border:1px solid #c1af7e;background:#f9f2ddf0;box-shadow:0 2px 0 #856d4c44,0 5px 12px #1c38242a;white-space:nowrap;text-align:center;color:var(--ink);pointer-events:none}.building-label::before,.building-label::after{content:'';position:absolute;top:3px;bottom:3px;width:2px;background:#b9a77c}.building-label::before{left:3px}.building-label::after{right:3px}.building-label strong{font-family:'SimSun',serif;font-size:14px;letter-spacing:.07em;display:block;line-height:1.35}.building-label small{display:block;font-size:8px;color:#7e8069;margin-top:1px}.is-tower .building-label{background:#2c5749ed;border-color:#d3c28d;color:#fff1c9}.is-tower .building-label small{color:#d5d8bd}.map-caption{position:absolute;left:3%;bottom:6%;display:flex;gap:10px;align-items:center;color:#496452;opacity:.85;pointer-events:none}.map-compass{font-size:36px}.map-caption>span:last-child{font:16px 'SimSun',serif;letter-spacing:.12em}.map-caption small{display:block;font:9px system-ui;letter-spacing:0;margin-top:4px}.smoke{position:absolute;left:49%;top:16%;pointer-events:none}.smoke i{position:absolute;width:4px;height:5px;background:#ebeed5aa;animation:smoke-rise 3s linear infinite}.smoke i:nth-child(2){animation-delay:1s;left:4px}.smoke i:nth-child(3){animation-delay:2s;left:-4px}@keyframes smoke-rise{0%{transform:translateY(0);opacity:0}20%{opacity:.8}100%{transform:translateY(-25px);opacity:0}}
.city-navigation{display:flex;justify-content:center;gap:2px;margin:4px auto 14px}.city-navigation button{display:flex;align-items:center;gap:7px;padding:8px 15px;border:0;background:transparent;color:#526751;font-size:11px}.city-navigation button:hover{background:#f8f1dcaa;color:var(--jade)}.city-navigation .game-icon{width:16px;height:16px}.city-bottom{max-width:1100px;margin:0 auto}.sect-status{display:flex;gap:22px;padding:0 4px 10px;font-size:10px;color:#6b7b66}.sect-status i{display:inline-block;width:5px;height:5px;margin-right:6px;background:#6c8a55}.tower-record{margin-left:auto}.tower-record b{font-size:14px;color:var(--jade);margin-inline:5px}.injury-note{color:var(--danger)}.last-run{max-width:1100px;margin:16px auto 0;display:flex;justify-content:space-between;align-items:center;gap:12px}.last-run span{display:inline-block;margin-left:14px;font-size:12px}
@media(max-width:1000px){.city-page{padding:20px}.city-map{max-width:min(100%,calc((100dvh - 340px) * 1.5))}.building-label{padding:4px 9px;min-width:85px}.building-label strong{font-size:12px}.building-label small{font-size:8px}}
@media(max-width:640px){.city-page{padding:16px 12px 18px}.city-topline{align-items:flex-start;gap:6px}.city-topline h2{font-size:13px;letter-spacing:.03em}.city-topline .eyebrow{font-size:6px}.city-topline>.btn{font-size:10px;padding:7px;min-height:36px}.city-topline>.btn>.game-icon{display:none}.city-viewport{overflow-x:auto;justify-content:flex-start;scrollbar-width:thin;scrollbar-color:#b2b89b transparent;margin:0 -12px;padding:0 15px 14px}.city-map{width:680px;min-width:680px;max-width:none;flex:none}.building-label strong{font-size:13px}.building-label small{font-size:9px}.city-navigation{margin:3px 0 13px;gap:0;justify-content:space-between}.city-navigation button{flex-direction:column;gap:4px;padding:7px 8px;min-width:44px;font-size:10px}.city-navigation .game-icon{width:20px;height:20px}.sect-status{gap:14px;font-size:9px;padding:0 3px 9px}.tower-record,.map-caption{display:none}.last-run{font-size:12px}.last-run span{margin-left:0;margin-right:10px}}
.environment-bar{display:flex;align-items:center;justify-content:space-between;gap:16px;max-width:1100px;margin:0 auto 9px;color:#536c57;font-size:12px}.environment-bar>span{display:flex;align-items:center;gap:8px}.environment-bar i{width:7px;height:7px;background:#b49957;border-radius:50%;box-shadow:0 0 7px #c2ac6e77}.environment-bar small{color:#7b856f;font-size:11px}.environment-bar label{display:flex;align-items:center;gap:7px}.environment-bar select{font-size:12px;min-height:32px;padding:3px 25px 3px 10px;background:#f9f3e4b0;border-color:#bfc3aa}
.city-topline{max-width:1100px}.city-topline .eyebrow{font-size:10px}.city-map{max-width:min(1100px,calc((100dvh - 360px) * 1.5));min-width:640px}.city-background{filter:brightness(var(--day-brightness,1)) saturate(var(--day-saturation,1));transition:filter 3s ease;mask-image:linear-gradient(to bottom,transparent,#000 3%,#000 95%,transparent)}.building-label{bottom:-12px;min-width:142px;max-width:210px;padding:6px 11px;white-space:normal}.building-label strong{font-size:15px}.building-label small{font-size:10px;line-height:1.5;color:#626e59;white-space:nowrap}.building-label small:last-child{font-size:9px;max-width:190px;white-space:normal}.building-hotspot:hover .building-label,.building-hotspot:focus-visible .building-label{border-color:#658a69;box-shadow:0 0 0 2px #e5d8a8,0 6px 14px #183e3040}.map-caption{display:none}.city-navigation button{font-size:13px;min-height:44px}.sect-status{font-size:11px}
@media(max-width:1000px){.city-map{min-width:620px;max-width:min(100%,calc((100dvh - 370px) * 1.5))}.building-label{min-width:130px}.building-label strong{font-size:14px}.building-label small{font-size:10px}.city-navigation button{padding-inline:12px}}
@media(max-width:640px){.environment-bar{margin:0 0 7px;font-size:11px}.environment-bar small{font-size:10px}.environment-bar select{min-height:36px}.city-map{width:760px;min-width:760px;max-width:none}.city-topline h2{font-size:14px}.city-topline .eyebrow{font-size:8px;letter-spacing:.13em}.building-label{min-width:134px}.city-navigation{gap:0}.city-navigation button{padding:6px 4px;min-width:44px;font-size:11px}.city-navigation .game-icon{width:18px;height:18px}.sect-status{font-size:10px;gap:10px}}
</style>
