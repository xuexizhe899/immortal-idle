<script setup lang="ts">
import { computed,nextTick,ref,watch } from 'vue'
import { snapshotDiscipleImage,enemyImage } from '../presentation/assetPaths'
import { resourceName,snapshotAffixes,snapshotEncounter,type DisplayCatalog } from '../presentation/gameText'
import { equipmentSlotNames } from '../presentation/equipment'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import BattleStage from '../rendering/BattleStage.vue'
import ConquestRun from './ConquestRun.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import GearIcon from '../components/game/GearIcon.vue'
import PanelModal from '../components/ui/PanelModal.vue'
defineEmits<{returnCity:[]}>()
const store=useGameStore();const catalog=computed(()=>store.catalog as DisplayCatalog|null);const run=computed(()=>store.run?.run);const playing=ref(false)
const statusNames:Record<string,string>={choosing_node:'选择前行之路',choosing_affix:'领悟新的道法',defeated:'此行暂歇',cleared:'此行功成'}
const statusLabel=computed(()=>statusNames[store.status]??'整装待发')
const party=computed(()=>(run.value?.party??[]).map(id=>{const fixed=run.value?.party_snapshot?.combatants.find(d=>d.id===id);const d=store.disciples.find(d=>d.id===id);const template=d?.template_id??id;return{id,name:fixed?.name??catalog.value?.disciples[template]?.name??id,image:snapshotDiscipleImage(fixed?.asset_id,template,catalog.value)}}))
const layers=computed(()=>run.value?.nodes?.length??0)
const total=computed(()=>Number(run.value?.party_snapshot?.mode.node_count??0))
const fixedRoutes=computed(()=>(run.value?.party_snapshot?.route_version??1)>=2)
const modeId=computed(()=>run.value?.mode??'tower')
const worldNode=computed(()=>run.value?.party_snapshot?.mode.world_node as Record<string,unknown>|undefined)
const modeName=computed(()=>String(worldNode.value?.name??(modeId.value==='expedition'?'远行':modeId.value==='dungeon'?'秘境试炼':modeId.value==='world'?'外域交锋':`问道塔 · ${run.value?.tower_tier ?? 1} 阶`)))
const enemyArmyLabel=computed(()=>modeId.value==='dungeon'?'秘境守敌':modeId.value==='world'?['invasion','raid','critical'].includes(String(worldNode.value?.kind))?'来犯外敌':'守关敌阵':undefined)
const stepUnit=computed(()=>modeId.value==='expedition'?'段':modeId.value==='dungeon'||modeId.value==='world'?'关':'层')
const modeBest=computed(()=>modeId.value==='expedition'?(store.state?.expedition_floor??0):(run.value?.tower_tier && run.value.tower_tier>1 ? store.state?.tower_tiers[String(run.value.tower_tier)]??0 : store.state?.tower_floor??0))
const hpPercent=computed(()=>run.value?.max_hp?Math.max(0,run.value.hp/run.value.max_hp*100):0)
const affixDefinitions=computed(()=>snapshotAffixes(run.value?.party_snapshot?.affix_pool))
const groupCounts=computed(()=>{const counts:Record<string,number>={};for(const id of run.value?.affixes??[]){const group=affixDefinitions.value[id]?.group;if(group)counts[group]=(counts[group]??0)+1}return counts})
const kinds:Record<string,string>={battle:'遭遇',elite:'强敌',boss:'首领',rest:'补给',event:'机缘'}
const routeChoices=computed(()=>(run.value?.choices??[]).map(node=>{
  const roster=snapshotEncounter(node,run.value?.party_snapshot,layers.value)
  return {...node,roster,peaceful:node.kind==='rest'||node.kind==='event',description:'description' in node?String(node.description??''):'',enemyCount:roster.reduce((count,enemy)=>count+enemy.count,0)}
}))
const ended=computed(()=>store.status==='cleared'||store.status==='defeated')
const decisionOpen=ref(false)
const decisionTrigger=ref<HTMLButtonElement|null>(null)
const infoTab=ref('loot')
const decisionKind=computed(()=>run.value?.sect_id ? '' : store.status==='choosing_node' ? 'route' : store.status==='choosing_affix' ? 'affix' : '')
const decisionKey=computed(()=>run.value&&decisionKind.value ? `${store.slotId}:${run.value.run_seed}:${layers.value}:${decisionKind.value}` : '')
const canDecide=computed(()=>!!decisionKey.value&&!store.busy&&!playing.value)
let promptedDecision=''
watch([() => store.slotId, () => run.value?.run_seed], () => {
  decisionOpen.value=false
  infoTab.value='loot'
  promptedDecision=''
}, { flush:'sync' })
watch([decisionKey, playing, () => store.busy], async ([key]) => {
  if (!key || playing.value) { decisionOpen.value=false; return }
  if (store.busy) return
  // 等战场接收新战报并确认演出结束；同一次选择手动关闭后不再反复弹出。
  await nextTick()
  if (key!==decisionKey.value || !canDecide.value || promptedDecision===key) return
  promptedDecision=key
  decisionOpen.value=true
}, { immediate:true, flush:'post' })
watch(decisionKey, () => { decisionOpen.value=false }, { flush:'sync' })
function openDecision() {
  if (!canDecide.value) return
  promptedDecision=decisionKey.value
  decisionOpen.value=true
}
function closeDecision() {
  decisionOpen.value=false
  nextTick(() => decisionTrigger.value?.focus({ preventScroll:true }))
}
async function chooseRoute(index:number) {
  if (!canDecide.value || decisionKind.value!=='route' || !routeChoices.value[index]) return
  await store.choose(index)
}
async function chooseAffix(id:string) {
  if (!canDecide.value || decisionKind.value!=='affix' || !run.value?.affix_options.includes(id)) return
  await store.pickAffix(id)
}
const activeBonds=computed(()=>run.value?.party_snapshot?.bonds??[])
const bondNames=computed(()=>Object.fromEntries(activeBonds.value.map(bond=>[bond.id,bond.name])))
// 道法可改变本局气血上限，逐人只展示服务端记录的当前气血，不以出发快照充当上限。
const partyVitals=computed(()=>party.value.map(member=>({...member,hp:run.value?.member_hp[member.id]??0})))
const hasPartyVitals=computed(()=>partyVitals.value.length>0&&partyVitals.value.every(member=>Object.hasOwn(run.value?.member_hp??{},member.id)))
const actionHint=computed(()=>playing.value?'正在播放交锋，可在战场中跳过后继续。':store.busy?'正在确认本次选择，请稍候。':store.status==='choosing_affix'?'点选一项道法立即领悟，随后继续前行。':'点选一条路线立即前往；敌情与收益可在卡片中查看。')
const lastWasPeaceful=computed(()=>['rest','event'].includes(run.value?.nodes.at(-1)?.kind??''))
const lootNote=computed(()=>run.value?.practice?'演练不发放正式战利品。':modeId.value==='dungeon'?'秘境失败仍可带回此前已取得的装备与材料。':modeId.value==='tower'?'途中已获得的装备会在结算时全部带回；落败时资源仍按规则折算。':worldNode.value?'挑战结束后统一结算，收益以结算结果为准。':'待出征结束后带回；落败按规则折算部分收益。')
const endingTitle=computed(()=>run.value?.practice?'演练结束，再研招式':store.status!=='cleared'?'暂别行程，整顿再来':worldNode.value?'此行告捷，历练有成':modeId.value==='expedition'?'远行抵达，满载而归':'登临绝顶，问道功成')
const endingDescription=computed(()=>{
  if(run.value?.practice)return '本次演练不发放正式奖励。结算后可调整阵容，再次验证招式与配装。'
  const progress=worldNode.value?`此次完成 ${layers.value} ${stepUnit.value}。`:`此次到达 ${layers.value} ${stepUnit.value}，${modeName.value}最高记录 ${modeBest.value} ${stepUnit.value}。`
  if(store.status==='cleared')return `${progress}将战利品带回宗门，开启下一段修行。`
  const reason=run.value?.end_reason==='round_limit'?'二十轮已尽，未能击败敌人。':''
  return `${progress}${reason}${modeId.value==='dungeon'?'此前已取得的装备与材料会随结算带回，可先在较低片区补装、强化或疗伤。':modeId.value==='tower'?'途中已获得的装备会随结算全部带回，资源按规则折算；可先回宗门疗伤、强化后再来。':worldNode.value?'可先演练试阵，或到较低片区刷装培养后再来挑战。':'保留部分收益，结算后可回宗门疗伤。'}`
})
function bondSkillNames(skillIds:string[]){return [...new Set(skillIds)].map(id=>run.value?.party_snapshot?.combatants.map(unit=>unit.active).find(skill=>skill.id===id)?.name??catalog.value?.skills[id]?.name??id).join(' · ')}
</script>
<template><ConquestRun v-if="run?.sect_id" @return-city="$emit('returnCity')" /><div v-else-if="run" class="run-page">
  <div class="run-title" :data-seal="ended?'归':modeId==='tower'?'问':'行'"><div><span class="eyebrow">{{ modeId==='expedition'?'远行纪事':worldNode?'山河历练':'问道试炼' }}</span><h2>{{ modeName }} <span>第 {{ Math.min(layers+(store.status==='choosing_node'?1:0),total||Infinity) }} {{ stepUnit }}</span></h2><p class="muted">{{ statusLabel }} · 出征进度会自动保存</p><span v-if="run.practice" class="badge badge-muted practice-badge">演练 · 无正式奖励</span></div><div class="run-title-actions"><button class="btn btn-small" :disabled="store.busy" @click="$emit('returnCity')"><GameIcon name="home" />返回宗门</button><div class="tower-count"><strong>{{ layers }}</strong><span>/ {{ total }} {{ stepUnit }}</span></div></div></div>
  <div class="floor-progress" :aria-label="`已完成${layers}/${total}${stepUnit}`"><span v-for="i in total" :key="i" :class="{done:i<=layers,current:i===layers+1&&!ended,boss:i===total}"><i></i><small v-if="i%5===0||i===1">{{ i }}</small></span></div>
  <div class="run-health"><div><GameIcon name="leaf" /><strong>当前同道气血</strong><span>{{ run.hp }} / {{ run.max_hp }}</span></div><div class="progress-track"><span :style="{width:`${hpPercent}%`}"></span></div></div>
  <details v-if="hasPartyVitals" class="party-vitals" :open="lastWasPeaceful"><summary>随行弟子 · {{ partyVitals.filter(member=>member.hp>0).length }} / {{ party.length }} 人可战 <span>查看逐人气血</span></summary><div><article v-for="member in partyVitals" :key="member.id" :class="{fallen:member.hp===0}"><img :src="member.image" alt="" class="pixel-art"/><strong>{{ member.name }}</strong><span>气血 {{ member.hp }}</span></article></div></details>
  <p v-if="lastWasPeaceful" class="battle-context">{{ run.nodes.at(-1)?.kind==='rest'?'调息已完成':'机缘已取得' }}，上方为当前气血。下方保留最近一场交锋战报。</p>
  <section v-if="decisionKind" class="run-decision-bar" aria-label="下一步行动">
    <div><strong>{{ decisionKind==='route' ? '选择前行路线' : '领悟新的道法' }}</strong><p role="status">{{ playing ? '交锋演出结束后继续，也可在战场中跳过。' : store.busy ? '正在确认本次选择，请稍候。' : decisionKind==='route' ? `第 ${layers+1} ${stepUnit} · 查看敌情与收益，选择下一步。` : '从本次道法中择一领悟，再继续前行。' }}</p></div>
    <button ref="decisionTrigger" class="btn btn-primary" :disabled="!canDecide" aria-haspopup="dialog" :aria-expanded="decisionOpen" @click="openDecision"><GameIcon :name="decisionKind==='route'?'sword':'star'" />{{ decisionKind==='route'?'选择路线':'领悟道法' }}</button>
  </section>
  <section v-if="ended" class="run-ending paper"><span class="eyebrow">{{ run.practice?'演练复盘':store.status==='cleared'?'修行有成':'此行暂歇' }}</span><h3>{{ endingTitle }}</h3><p>{{ endingDescription }}</p><p v-if="playing" class="decision-hint" role="status">交锋演出尚未结束，可在战场中跳过后结算。</p><button class="btn btn-primary" :disabled="store.busy||playing" @click="store.settleRun()"><GameIcon name="bag" />{{ store.busy?'正在结算…':'结算并返回宗门' }}</button></section>
  <BattleStage :title="`${modeName} · ${store.battleResult?'最近交锋':'整装待发'}`" :enemy-label="enemyArmyLabel" :party="party" :result="store.battleResult" :bond-names="bondNames" @playing="playing=$event" />
  <section class="run-info" aria-label="此行记录">
    <nav class="run-info-tabs" aria-label="查看此行记录"><button :class="{active:infoTab==='loot'}" :aria-pressed="infoTab==='loot'" @click="infoTab='loot'">此行战利品</button><button :class="{active:infoTab==='bonds'}" :aria-pressed="infoTab==='bonds'" @click="infoTab='bonds'">战斗羁绊 <small>{{ activeBonds.length }}</small></button><button :class="{active:infoTab==='arts'}" :aria-pressed="infoTab==='arts'" @click="infoTab='arts'">已悟道法 <small>{{ run.affixes?.length ?? 0 }}</small></button></nav>
    <div class="run-info-content" :key="infoTab" tabindex="0" :aria-label="infoTab==='loot'?'此行战利品':infoTab==='bonds'?'战斗羁绊':'已悟道法'">
  <section v-if="infoTab==='loot'" class="run-supply"><span class="eyebrow">行囊 · 尚待结算</span><h3>此行战利品</h3><div v-for="(n,key) in run.pending_loot" :key="key" class="loot-row"><span>{{ resourceName(key,catalog) }}</span><strong>{{ number(n,1) }}</strong></div><p v-if="!Object.keys(run.pending_loot??{}).length&&!run.pending_gear?.length" class="muted">{{ run.practice?'演练只记录交锋，不发放战利品。':'沿路所得将在此累积。' }}</p><div v-if="run.pending_gear?.length" class="gear-spoils"><h4>已获装备 <span>{{ run.pending_gear.length }} 件</span></h4><article v-for="gear in run.pending_gear" :key="gear.id"><GearIcon :slot="gear.slot" :size="28" /><div><strong>{{ gear.name }}</strong><small>{{ gear.tier }} 阶 · {{ equipmentSlotNames[gear.slot]??gear.slot }}</small></div></article></div><p class="loot-note">{{ lootNote }}</p></section>
  <section v-else-if="infoTab==='bonds'" class="run-bonds"><div class="section-heading"><h3>战斗羁绊</h3><span class="badge">{{ activeBonds.length }}</span></div><article v-for="bond in activeBonds" :key="bond.id"><strong>{{ bond.name }}</strong><p>{{ bondSkillNames(bond.modifiers.map(modifier=>modifier.skill)) }}</p><small>本局已激活 · 施招时按条件联动</small></article><p v-if="!activeBonds.length" class="muted">此行未组成具名战斗羁绊，仍可通过护盾、治疗和降防相互配合。</p></section><section v-else class="run-build"><div class="section-heading"><h3>已悟道法</h3><span class="badge">{{ run.affixes?.length }}</span></div><article v-for="(id,i) in run.affixes" :key="`${id}-${i}`"><span class="build-group">{{ affixDefinitions[id]?.groupName??'' }}</span><strong>{{ affixDefinitions[id]?.name??id }}</strong><p>{{ affixDefinitions[id]?.description??'本局未记录道法说明' }}</p></article><p v-if="!run.affixes?.length" class="muted">沿途领悟道法，逐步组成此行招式。</p></section></div></section>
  <PanelModal v-if="decisionOpen && decisionKind" :title="decisionKind==='route'?'选择路线':'领悟道法'" :subtitle="`${modeName} · 第 ${decisionKind==='route'?layers+1:layers} ${stepUnit}`" wide @close="closeDecision">
  <section v-if="decisionKind==='route'" class="decision-section">
    <div class="section-heading"><div><span class="eyebrow">下一步 · 选择路线</span><h3>{{ routeChoices.length>1?'前路有岔，各循其道':'前路已明，整装前行' }}</h3></div><span class="badge">{{ layers+1 }} / {{ total }} {{ stepUnit }}</span></div>
    <p class="decision-hint" :class="{locked:store.busy||playing}" role="status">{{ actionHint }}</p>
    <div class="node-choices">
      <button v-for="(node,index) in routeChoices" :key="`${node.enemy}-${index}`" class="node-card" :class="node.kind" :disabled="!canDecide" @click="chooseRoute(index)">
        <GameIcon :name="node.kind==='rest'?'leaf':node.kind==='event'?'star':node.kind==='boss'?'tower':'sword'" />
        <span class="badge" :class="node.kind==='battle'?'badge-muted':'badge-gold'">{{ kinds[node.kind]??node.kind }}</span>
        <h4>{{ node.kind==='rest'?'歇脚调息':node.kind==='event'?'寻访机缘':node.enemyCount?`${node.enemyCount} 名敌人`:'编成尚未记录' }}</h4>
        <p v-if="node.description" class="node-description">{{ node.description }}</p>
        <p v-if="fixedRoutes&&!node.peaceful">基础战力 {{ number(node.power) }} <small>仅作参考，招式配合决定交锋表现</small></p>
        <div class="enemy-roster">
          <span v-for="enemy in node.roster" :key="enemy.id" class="enemy-chip"><img v-if="enemyImage(enemy.id)" :src="enemyImage(enemy.id)" alt="" loading="lazy" />{{ enemy.name }}<small v-if="enemy.count>1">×{{ enemy.count }}</small></span>
        </div>
        <div class="node-threats"><p v-for="enemy in node.roster" :key="enemy.id"><strong>{{ enemy.name }}</strong>：{{ enemy.threats.join('；')||'本局未记录招式说明' }}</p></div>
        <div class="node-loot"><strong>{{ node.peaceful?'此处可获':'胜利所得' }} · 结算时带回</strong><span v-for="(n,key) in node.reward" :key="key">{{ resourceName(key,catalog) }} +{{ number(n,2) }}</span><span v-if="!Object.keys(node.reward).length">{{ node.kind==='rest'?'恢复效果见本条路线说明':'沿路所得以探索结果为准' }}</span></div>
        <span class="node-enter">{{ store.busy?'正在确认…':playing?'等待演出结束':node.peaceful?'前往此处':'确认挑战' }} <GameIcon name="chevron" /></span>
      </button>
    </div>
  </section>
  <section v-else-if="decisionKind==='affix'" class="decision-section"><div class="section-heading"><div><span class="eyebrow">下一步 · 领悟道法</span><h3>一念通明，择一而行</h3></div></div><p class="muted">此行道法仅在本次出征生效，同组词条可形成协同。</p><p class="decision-hint" :class="{locked:store.busy||playing}" role="status">{{ actionHint }}</p><div class="affix-choices"><button v-for="id in run.affix_options" :key="id" class="affix-card" :class="{resonating:(groupCounts[affixDefinitions[id]?.group??'']??0)>0}" :disabled="!canDecide" @click="chooseAffix(id)"><span class="affix-symbol">悟</span><span class="badge badge-gold">{{ affixDefinitions[id]?.groupName??'' }}</span><h4>{{ affixDefinitions[id]?.name??id }}</h4><p>{{ affixDefinitions[id]?.description??'本局未记录道法说明' }}</p><small>已有同组 {{ groupCounts[affixDefinitions[id]?.group??'']??0 }} 项</small><span class="affix-pick">{{ store.busy?'正在领悟…':playing?'等待演出结束':'领悟此道' }} <GameIcon name="chevron" /></span></button></div></section>
  </PanelModal>
</div></template>
<style scoped>
.run-decision-bar{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;align-items:center;gap:18px;padding:12px 16px;margin-bottom:14px;background:#edf0dc;border:1px solid #a9ba96;border-left:4px solid #b38a46;box-shadow:0 3px 0 #8c684426}.run-decision-bar>div{min-width:0}.run-decision-bar strong{font:18px 'SimSun',serif;color:var(--jade)}.run-decision-bar p{margin:5px 0 0;font-size:12px;line-height:1.6;color:var(--muted)}.run-decision-bar>.btn{flex:none;min-height:44px}
.run-info{margin-top:18px;border:1px solid #b9ab86;background:#f6f1df;box-shadow:inset 3px 0 #8c68441a}.run-info-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;padding:6px;border-bottom:1px solid #b9ab86;background:#e9e6d0}.run-info-tabs button{min-width:0;min-height:44px;padding:8px;border:1px solid transparent;background:transparent;color:var(--muted);font-size:13px}.run-info-tabs button.active{border-color:#326c55;background:#326c55;color:#f6f1df;box-shadow:inset 0 -2px #b38a46}.run-info-tabs small{margin-left:4px;font-size:11px;font-variant-numeric:tabular-nums}.run-info-content{max-height:360px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:18px 20px}.run-info-content:focus-visible,.run-info-tabs button:focus-visible{outline:2px solid var(--jade);outline-offset:-2px}
@media(max-width:720px){.run-decision-bar{gap:10px;padding:10px 12px}.run-decision-bar strong{font-size:16px}.run-decision-bar p{font-size:11px}.run-decision-bar>.btn{padding-inline:12px;font-size:12px}.run-info-tabs{padding:4px;gap:2px}.run-info-tabs button{padding-inline:4px;font-size:12px}.run-info-tabs small{margin-left:2px;font-size:10px}.run-info-content{padding:14px;max-height:340px}}
.run-page{max-width:1400px;margin:0 auto;padding:28px 40px 50px}.run-title{position:relative;display:flex;justify-content:space-between;align-items:center;gap:18px;padding:14px 18px 14px 67px;border:1px solid #b9af8d;border-left:4px solid #326c55;background:#f6f1df;box-shadow:inset 0 -3px #8c684420}.run-title h2{font-size:27px;letter-spacing:.1em;margin:4px 0}.run-title h2>span{font:13px system-ui;color:var(--muted);letter-spacing:0;margin-left:16px}.run-title p{margin:0}.tower-count{display:flex;align-items:baseline;gap:8px}.tower-count strong{font:40px 'SimSun',serif;color:var(--jade)}.tower-count span{font-size:12px;color:var(--muted)}.floor-progress{display:flex;margin:14px 0 31px;gap:5px}.floor-progress>span{position:relative;flex:1;height:6px;background:#d2d9bf;border-bottom:1px solid #bcc5a9}.floor-progress>span.done{background:#326c55;border-color:#213f36}.floor-progress>span.current{background:#b38a46;border-color:#8c6844;box-shadow:0 0 0 2px #b38a4622}.floor-progress small{position:absolute;top:9px;left:50%;font-size:8px;color:var(--muted)}.floor-progress .boss{background:#baa77a}.run-health{margin-bottom:12px;padding:11px 14px;border:1px solid #bdc9a9;border-left:3px solid #6d9666;background:#e6ecd8}.run-health>div:first-child{display:flex;align-items:center;gap:8px;font-size:11px;margin-bottom:7px;color:var(--jade)}.run-health .game-icon{width:15px;height:15px}.run-health span{margin-left:auto;font-size:11px;color:var(--muted)}.run-health .progress-track{height:7px;background:#c5d1b2;box-shadow:inset 0 1px 1px #213f3622}.run-health .progress-track>span{background:#326c55;border-right:2px solid #a1b88c}.decision-section{margin:0}.decision-section .eyebrow{font-size:8px}.decision-section h3{font-size:21px;margin-top:4px}.decision-section>.muted{margin-top:-5px}.node-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.node-card{position:relative;display:flex;flex-direction:column;align-items:flex-start;text-align:left;padding:21px;background:#f6f1df;border:1px solid #b9ad88;border-top:4px solid #78936a;box-shadow:0 3px 0 #8c684426;transition:border-color .15s,background .15s}.node-card:hover:not(:disabled){border-color:var(--jade);background:#f7f6e7}.node-card>.game-icon{width:29px;height:29px;color:#8c9a77;margin-bottom:14px}.node-card.elite>.game-icon,.node-card.boss>.game-icon{color:#a57d41}.node-card h4{font-size:21px;margin:11px 0 8px}.node-card>p{font-size:11px;color:var(--muted);margin-bottom:15px}.node-card>p b{color:var(--ink);font-size:15px;margin-left:5px}.node-loot{display:flex;flex-direction:column;gap:5px;font-size:10px;color:#687e5e;padding:10px 0 17px;border-top:1px solid #d8cfb5;width:100%}.node-enter,.affix-pick{margin-top:auto;display:flex;align-items:center;justify-content:space-between;width:100%;font-size:11px;color:var(--jade)}.node-enter>.game-icon,.affix-pick>.game-icon{width:15px;height:15px}.affix-choices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.affix-card{position:relative;display:flex;flex-direction:column;align-items:flex-start;text-align:left;min-height:265px;padding:20px 15px;border:1px solid #c4b78f;background:linear-gradient(#f3ecd6,#fcf7e9)}.affix-card:hover:not(:disabled){border-color:var(--jade);box-shadow:0 0 0 2px #73966122}.affix-symbol{font:40px 'SimSun',serif;color:#c0ad75;align-self:center;margin-bottom:13px}.affix-card>.badge{font-size:9px}.affix-card h4{font-size:21px;margin:9px 0}.affix-card p{font-size:11px;color:var(--jade);margin-bottom:8px}.affix-card small{color:var(--muted);font-size:9px;margin-bottom:20px}.affix-pick{padding-top:12px;border-top:1px solid #d5c9a9}.run-info h3{font-size:18px;margin:4px 0 18px}.run-supply>.eyebrow{font-size:7px}.loot-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #d9cfb4;font-size:11px}.loot-row strong{font-weight:500;color:var(--jade)}.loot-note{font-size:9px;color:var(--muted);margin:15px 0 0}.run-bonds article{border-top:1px solid #d9cfb4;padding:10px 0}.run-bonds article strong{font:14px 'SimSun',serif;color:var(--jade)}.run-bonds article p{font-size:11px;margin:4px 0}.run-bonds article small{font-size:9px;color:var(--gold)}.run-build .section-heading{margin-bottom:10px}.run-build .section-heading h3{margin:0}.run-build article{border-top:1px solid #d9cfb4;padding:12px 0}.build-group{display:block;font-size:8px;color:var(--gold)}.run-build article>strong{font:14px 'SimSun',serif}.run-build article>p{font-size:10px;color:var(--jade);margin:5px 0 0}.run-ending{position:relative;margin:0 0 16px;text-align:left;padding:16px 20px;border:1px solid #b7aa80;border-left:4px solid #b38a46;background:#f6f1df;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 20px;align-items:center}.run-ending h3{font-size:24px;margin:0;grid-column:1}.run-ending p{font-size:12px;line-height:1.8;color:var(--muted);margin:0;grid-column:1}.run-ending>.eyebrow{grid-column:1}.run-ending>.btn{grid-column:2;grid-row:1 / 5;min-height:48px}
.enemy-roster{display:flex;flex-wrap:wrap;gap:4px;width:100%;padding:0 0 12px}.enemy-chip{display:inline-flex;align-items:center;gap:4px;padding:2px 6px 2px 3px;background:#e8e4d2;border:1px solid #d0c7ac;font-size:9px;color:#5f6d54;white-space:nowrap}.enemy-chip img{width:18px;height:22px;object-fit:contain;object-position:center bottom;image-rendering:pixelated}.enemy-chip small{color:#9a7a3f;font-size:8px}
@media(max-width:1000px){.run-page{padding:24px}.affix-choices{gap:8px}.affix-card{padding:16px 11px}}
@media(max-width:720px){.run-page{padding:20px 14px 36px}.run-title h2{font-size:23px}.run-title h2>span{display:block;margin:4px 0 0;font-size:11px}.run-title .eyebrow{font-size:7px}.tower-count strong{font-size:31px}.floor-progress{gap:3px;margin-bottom:33px}.node-card{padding:17px 14px}.node-card h4{font-size:19px}.decision-section h3{font-size:19px}.decision-section .section-heading>.muted{display:none}.affix-choices{grid-template-columns:1fr}.affix-card{min-height:0;display:grid;grid-template-columns:55px 1fr auto;gap:5px 10px;align-items:center;padding:16px}.affix-symbol{grid-row:1 / 5;margin:0;font-size:33px}.affix-card>.badge{grid-column:2;width:fit-content}.affix-card h4{grid-column:2;font-size:20px;margin:4px 0}.affix-card p{grid-column:2;margin:0}.affix-card small{grid-column:2;margin:3px 0 0}.affix-pick{grid-column:3;grid-row:1 / 5;border:0;padding:0;font-size:0}.affix-pick .game-icon{width:20px;height:20px}.run-info h3{font-size:16px}.run-ending h3{font-size:22px}.run-ending .eyebrow{font-size:7px}.run-ending>.btn{width:100%}}
@media(max-width:720px){.enemy-chip{font-size:8px}.enemy-chip img{width:15px;height:19px}}
.node-threats{width:100%;margin-bottom:14px;font-size:10px;color:var(--muted);overflow-wrap:anywhere}.node-threats p{margin:0 0 7px;line-height:1.6}.node-threats strong{color:var(--ink);font-weight:500}.node-loot>strong{font-weight:500}
@media(max-width:520px){.node-choices{grid-template-columns:1fr}}
.run-title-actions{display:flex;align-items:center;gap:20px;flex-wrap:wrap;justify-content:flex-end}.run-title>div:first-child{min-width:0}.run-title h2{overflow-wrap:anywhere}.practice-badge{margin-top:9px}.party-vitals{margin:0 0 16px;border:1px solid #c2c9af;background:#edf0df}.party-vitals summary{padding:10px 13px;cursor:pointer;font-size:11px;color:var(--jade);min-height:40px}.party-vitals summary>span{float:right;color:var(--muted);font-size:10px}.party-vitals>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:0 12px 12px}.party-vitals article{min-width:0;background:#f6f1df;border:1px solid #bdc9a9;padding:8px;display:grid;grid-template-columns:30px minmax(0,1fr);gap:3px 8px;align-items:center}.party-vitals article>strong{display:block;font:14px 'SimSun',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.party-vitals article>span{font-size:10px;color:var(--muted);font-variant-numeric:tabular-nums}.party-vitals article.fallen{opacity:.65}.battle-context{margin:0;padding:10px 13px;font-size:11px;line-height:1.8;color:#6c775b;background:#f1ead5;border:1px solid #c9bd98;border-bottom:0}.decision-hint{padding:10px 12px;margin:0 0 14px;border-left:3px solid #75916e;background:#e8ecdc;color:var(--jade);font-size:11px;line-height:1.8}.decision-hint.locked{border-color:#b59654;background:#f2ead6;color:#7d663e}.node-card,.affix-card{min-width:0;overflow-wrap:anywhere}.node-card:disabled,.affix-card:disabled{opacity:.76}.node-card.rest{background:#edf0df;border-color:#b7c5a3}.node-card.event{background:#f5ebd5;border-color:#cbbb91}.node-card>p small{display:block;font-size:10px;color:#7a826c;margin-top:4px}.node-card>p.node-description{font-size:12px;line-height:1.8;color:var(--jade)}.node-card.rest>.game-icon{color:#5f8863}.node-card.event>.game-icon{color:#a48345}.node-enter,.affix-pick{font-weight:600;min-height:36px}.affix-card.resonating{border-top:3px solid #829265;background:linear-gradient(#e8ead4,#fcf7e9)}.affix-card.resonating small{color:var(--jade)}.gear-spoils{margin-top:16px;padding-top:12px;border-top:1px solid #c7bd9e}.gear-spoils h4{font:15px 'SimSun',serif;margin:0 0 9px;color:var(--jade)}.gear-spoils h4 span{float:right;font:10px system-ui;color:var(--muted)}.gear-spoils article{display:flex;gap:8px;align-items:center;border-top:1px solid #ded6bf;padding:9px 0}.gear-spoils .gear-icon{width:28px;height:28px}.gear-spoils article>div{min-width:0}.gear-spoils article strong{display:block;font:14px 'SimSun',serif;overflow-wrap:anywhere}.gear-spoils article small{display:block;font-size:10px;color:var(--muted);margin-top:3px}
@media(max-width:720px){.run-title{align-items:flex-start;gap:12px}.run-title-actions{gap:9px;flex-direction:column-reverse;flex-shrink:0}.run-title h2{line-height:1.5}.party-vitals summary{min-height:44px;font-size:12px}.party-vitals summary>span{font-size:10px}.party-vitals>div{gap:6px;padding:0 9px 9px}.party-vitals article{padding:7px 6px}.party-vitals article>strong{font-size:13px}.party-vitals article>span{font-size:10px}.decision-hint,.battle-context{font-size:12px}.node-card>p,.node-threats,.node-loot{font-size:12px}.node-card>p small{font-size:11px}.enemy-chip{font-size:10px}.affix-card p{font-size:12px}.affix-card small{font-size:11px}.affix-pick{min-height:44px}.loot-row{font-size:12px}.loot-note{font-size:11px;line-height:1.8}.run-bonds article p,.run-build article>p{font-size:12px;line-height:1.8}}

.run-title::before{content:attr(data-seal);position:absolute;left:18px;top:50%;transform:translateY(-50%);display:grid;place-items:center;width:34px;height:43px;border:1px solid #8c6844;box-shadow:inset 0 0 0 3px #f6f1df,inset 0 0 0 4px #b38a4680;color:#8c6844;font:26px SimSun,serif}.party-vitals article>img{grid-row:1 / 3;width:30px;height:44px;object-fit:contain;object-position:center bottom;background:#dfe8cf}.party-vitals article.fallen>img{filter:grayscale(1)}.party-vitals article>span{grid-column:2}.run-health>div:first-child>span{font-variant-numeric:tabular-nums;color:#326c55}.node-card.elite,.node-card.boss{border-top-color:#b38a46}.node-card.rest{border-top-color:#699866}.node-card.event{border-top-color:#a58b59}.node-card:focus-visible,.affix-card:focus-visible{outline:2px solid #326c55;outline-offset:3px}.affix-card{box-shadow:inset 0 0 0 4px #f6f1df,0 3px 0 #8c684426}.affix-symbol{border:1px solid #bba36e;padding:2px 7px;color:#8c6844;background:#ede7cd}.run-info-tabs button.active small{color:#e2d9ad}
@media(max-width:720px){.run-title{padding:12px 12px 12px 50px;gap:8px}.run-title::before{left:10px;width:27px;height:35px;font-size:21px}.run-title h2{font-size:21px;letter-spacing:.03em}.run-title-actions{gap:5px}.run-title-actions>.btn{font-size:11px;padding-inline:8px}.tower-count strong{font-size:27px}.run-health{padding:10px 11px}.party-vitals article{grid-template-columns:24px minmax(0,1fr);gap:3px 5px}.party-vitals article>img{width:24px;height:40px}.party-vitals article>strong{font-size:12px}.party-vitals article>span{font-size:9px;white-space:nowrap}.run-ending{display:block;padding:14px}.run-ending h3{margin:5px 0 8px;font-size:21px}.run-ending>.btn{margin-top:12px}.run-ending .decision-hint{margin-top:8px}}
@media(prefers-reduced-motion:reduce){.node-card,.affix-card{transition:none}}

</style>
