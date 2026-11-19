<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import DiscipleCard from '../components/game/DiscipleCard.vue'
import DiscipleEquipment from '../components/game/DiscipleEquipment.vue'
import DiscipleTraining from '../components/game/DiscipleTraining.vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import SkillDetails from '../components/game/SkillDetails.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import { discipleImage } from '../presentation/assetPaths'
import { effectText,injuryText,resourceName,leanNames,leanDescriptions,rarityNames,statNames,type DisplayCatalog,type DisplaySkill } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
const props=defineProps<{readOnly?:boolean;initialDiscipleId?:string}>()
const store = useGameStore()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const tab = ref('roster'); const filter = ref('all'); const selectedId = ref(''); const search = ref('')
const detailOpen = ref(false)
const detailTab = ref('overview')
const detailModal = ref<InstanceType<typeof PanelModal> | null>(null)
const onDuty = computed(() => new Set(store.state?.duty_slots?.map(s => s.disciple_id) ?? []))
const roster = computed(() => store.disciples.filter(d => { const template=catalog.value?.disciples[d.template_id]; return (!search.value || template?.name.includes(search.value)) && (filter.value==='all' || (filter.value==='hurt' ? d.injury_stacks>0 : filter.value==='duty' ? onDuty.value.has(d.id) : template?.lean===filter.value)) }))
const selected = computed(() => store.disciples.find(d => d.id === selectedId.value))
const selectedIndex = computed(() => roster.value.findIndex(d => d.id === selectedId.value))
const template = computed(() => selected.value ? catalog.value?.disciples[selected.value.template_id] : null)
const full = computed(() => store.party.length >= (catalog.value?.rules.max_party ?? 6))
const selectedParty = computed(() => !!selected.value && store.party.includes(selected.value.id))
const reason = computed(() => props.readOnly ? '出征期间阵容已锁定' : !selected.value ? '请选择弟子' : selected.value.busy ? '正在出征' : full.value && !selectedParty.value ? '出征队伍已满' : '')
const bonds = computed(() => Object.entries(catalog.value?.bonds ?? {}).filter(([id]) => template.value?.bonds?.includes(id)))
const partyTemplates = computed(() => new Set(store.party.map(id => store.disciples.find(d=>d.id===id)?.template_id)))
const recruitables = computed(() => Object.entries(catalog.value?.disciples ?? {}).filter(([,d])=>!search.value || d.name.includes(search.value)).sort((a,b)=>(a[1].unlock_cost?.reputation??0)-(b[1].unlock_cost?.reputation??0)))
const owned = computed(() => new Set(store.state?.unlocks ?? []))
const activeTraining = computed(() => store.training?.disciple_id === selected.value?.id ? store.training : null)
const trainingLoading = computed(() => store.trainingLoading && store.trainingFor === selected.value?.id)
const displayStats = computed(() => {
  const current = activeTraining.value?.current
  if (current) return { hp: current.health, atk: current.attack, def: current.defense, spd: current.speed }
  const stats = selected.value?.stats
  const base = template.value?.base_stats ?? {}
  return { hp: stats?.hp ?? base.hp, atk: stats?.atk ?? base.atk, def: stats?.def ?? base.def, spd: stats?.spd ?? base.spd }
})
const pillName = computed(() => catalog.value?.recipes?.['po_jing_dan']?.name ?? '破境丹')
function displayStat(key: string): number { return (displayStats.value as Record<string, number>)[key] ?? 0 }
function skill(value: string | DisplaySkill | undefined) { return typeof value === 'string' ? catalog.value?.skills?.[value] : value }
function isBattleBond(bond: NonNullable<DisplayCatalog>['bonds'][string]) { return bond.modifiers.length > 0 }
function countBond(members: string[], duty = false) { const templates = duty ? new Set(store.disciples.filter(d=>onDuty.value.has(d.id)).map(d=>d.template_id)) : partyTemplates.value; return members.filter(id=>templates.has(id)).length }
function scrollToRoster() { document.getElementById('disciple-roster')?.scrollIntoView({block:'nearest',behavior:'auto'}) }
function openDisciple(id: string, section = 'overview') {
  if (!store.disciples.some(disciple => disciple.id === id)) return
  selectedId.value = id
  detailTab.value = section
  detailOpen.value = true
}
function closeDisciple() { detailOpen.value = false }
function changeDisciple(direction: -1 | 1) {
  if (roster.value.length < 2) return
  const index = (selectedIndex.value + direction + roster.value.length) % roster.value.length
  selectedId.value = roster.value[index]!.id
}
function onDetailKey(event: KeyboardEvent) {
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
  const target = event.target as HTMLElement | null
  if (target?.closest('input, select, textarea, [contenteditable]:not([contenteditable="false"])')) return
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  changeDisciple(event.key === 'ArrowLeft' ? -1 : 1)
}
function goTrain(templateId: string) {
  const disciple = store.disciples.find(d => d.template_id === templateId)
  if (!disciple) { store.notice = '该弟子暂不可培养。'; return }
  tab.value = 'roster'
  filter.value = 'all'
  search.value = ''
  openDisciple(disciple.id, 'training')
}
watch(roster, list => { if (detailOpen.value && !list.some(d => d.id === selectedId.value)) closeDisciple() })
watch(() => store.slotId, () => { closeDisciple(); selectedId.value = '' })
watch(tab, value => { if (value !== 'roster') closeDisciple() })
watch([selectedId, detailTab], () => { nextTick(() => detailModal.value?.resetScroll()) })
watch(() => props.initialDiscipleId, id => {
  if (!id || !store.disciples.some(disciple => disciple.id === id)) return
  tab.value = 'roster'; filter.value = 'all'; search.value = ''; openDisciple(id)
}, { immediate: true })
watch([() => detailOpen.value ? selected.value?.id : undefined, () => store.revision], ([id]) => {
  if (id) void store.loadTraining(id)
}, { immediate: true })
</script>
<template>
  <header class="codex-heading"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 8h13q3 0 3 4 0-4 3-4h13v31H27q-3 0-3 3 0-3-3-3H8V8Z" /><path d="M24 12v25M13 15h6M13 21h6M13 27h6M29 15h6M29 21h6M29 27h6" /></svg><div><h3>{{ tab==='roster' ? '门下同道' : '访贤入山' }}</h3><p>{{ tab==='roster' ? '识其所长，授其器物，共修登仙之路。' : '以声望结识同道，让山门再添一席。' }}</p></div><span class="roster-total"><strong>{{ store.disciples.length }}</strong>位门人</span></header>
  <div class="tabs" role="tablist" aria-label="弟子管理"><button :class="{active:tab==='roster'}" role="tab" :aria-selected="tab==='roster'" @click="tab='roster'">门下弟子 <small>{{ store.disciples.length }}</small></button><button :class="{active:tab==='recruit'}" role="tab" :aria-selected="tab==='recruit'" @click="tab='recruit'">招贤纳士</button><input v-model="search" aria-label="查找弟子" placeholder="查找弟子" class="search-input" /></div>
  <template v-if="tab==='roster'">
    <details class="formation-editor"><summary><span class="formation-title">出征编队 <small>{{ store.party.length }} / {{ catalog?.rules.max_party ?? 6 }}</small></span><span class="formation-toggle"><span class="formation-expand">展开调整</span><span class="formation-collapse">收起编队</span><GameIcon name="chevron" /></span></summary><div class="formation-content"><p class="muted">顺序决定同身法出手与目标优先级</p><PartyStrip compact reorder @edit="scrollToRoster" /></div></details><div id="disciple-roster" class="roster-toolbar"><div class="filter-list"><button v-for="(label,id) in {all:'全部',attack:'攻',defense:'防',support:'辅',craft:'炼',duty:'值守',hurt:'受伤'}" :key="id" :class="{active:filter===id}" @click="filter=id">{{ label }}</button></div><span class="muted">出征阵容 {{ store.party.length }} / {{ catalog?.rules.max_party ?? 6 }}</span></div>
    <p class="roster-hint">点击弟子查看详情，可在弹窗中左右切换。</p>
    <div class="disciple-grid"><DiscipleCard v-for="d in roster" :key="d.id" :disciple="d" :name="catalog?.disciples[d.template_id]?.name ?? d.template_id" :selected="store.party.includes(d.id)" :active="detailOpen && selected?.id===d.id" :asset="discipleImage(d.template_id,catalog)" :lean="catalog?.disciples[d.template_id]?.lean" :rarity="catalog?.disciples[d.template_id]?.rarity" :duty="onDuty.has(d.id)" aria-haspopup="dialog" :aria-expanded="detailOpen && selected?.id===d.id" @toggle="openDisciple(d.id)" /><div v-if="!roster.length" class="empty-state"><strong>暂未寻得弟子</strong>调整筛选，或前往招贤纳士。</div></div>
  </template>
  <template v-else><div class="section-heading"><p class="muted">以声望访贤，邀同道入山。</p><span class="badge badge-gold">声望 {{ number(store.resources?.reputation) }}</span></div><div class="recruit-grid"><article v-for="[id,d] in recruitables" :key="id" class="recruit-card"><img :src="discipleImage(id,catalog)" :alt="d.name" class="pixel-art" loading="lazy" decoding="async" /><div><span class="eyebrow">{{ rarityNames[d.rarity] }} · {{ leanNames[d.lean] }}</span><h3>{{ d.name }} <small>{{ d.title }}</small></h3><p class="muted">{{ leanDescriptions[d.lean] }}</p><template v-if="owned.has(id)"><span class="badge">已拥有</span><button class="btn btn-small" :disabled="readOnly || store.busy" @click="goTrain(id)">前往培养</button></template><button v-else class="btn btn-small btn-primary" :disabled="readOnly || store.busy || (store.resources?.reputation ?? 0)<(d.unlock_cost?.reputation??0)" @click="store.recruit(id)">邀入宗门 · {{ number(d.unlock_cost?.reputation??0) }} 声望</button></div></article></div></template>
  <PanelModal v-if="detailOpen && selected && template" ref="detailModal" :title="template.name" subtitle="弟子详情" wide @close="closeDisciple" @keydown="onDetailKey">
    <template #actions>
      <nav class="disciple-switch" aria-label="切换弟子">
        <button class="btn btn-quiet" :disabled="roster.length<2" aria-label="上一位弟子" @click="changeDisciple(-1)"><GameIcon name="chevron" class="previous-disciple" /></button>
        <span aria-live="polite">{{ selectedIndex+1 }} / {{ roster.length }}</span>
        <button class="btn btn-quiet" :disabled="roster.length<2" aria-label="下一位弟子" @click="changeDisciple(1)"><GameIcon name="chevron" /></button>
      </nav>
    </template>
    <div class="disciple-detail">
      <nav class="detail-tabs" aria-label="弟子详情栏目"><button v-for="(label,id) in {overview:'概览',training:'培养',equipment:'装备',arts:'道法'}" :key="id" :class="{active:detailTab===id}" :aria-pressed="detailTab===id" @click="detailTab=id">{{ label }}</button></nav>
      <p v-if="readOnly" class="notice-box">出征尚未结算，可查阅详情；结算后可继续培养、换装与调整阵容。</p>
      <section v-if="detailTab==='overview'"><div class="detail-title"><svg class="identity-landscape" viewBox="0 0 420 190" fill="none" aria-hidden="true"><circle cx="303" cy="75" r="51" /><path d="m148 181 70-98 35 49 27-39 71 88M210 181l46-61 41 61M28 171h125M303 181h93M193 119l25-36 16 22" /></svg><div class="identity-copy"><span class="identity-title">{{ template.title }}</span><h3>{{ template.name }}</h3><div class="identity-tags"><span>{{ rarityNames[template.rarity] }}</span><span>{{ leanNames[template.lean] }}</span></div><p class="identity-level">境界 <strong>{{ selected.realm }}</strong><span>等级 {{ selected.level }}</span></p></div><img :src="discipleImage(selected.template_id,catalog)" :alt="template.name" class="detail-portrait pixel-art" /></div>
      <div class="attribute-heading"><span>人物基础属性</span><span>{{ selected.busy ? '正在出征' : onDuty.has(selected.id) ? '宗门值守中' : selected.injury_stacks ? '调养中' : '已入宗门' }}</span></div><div class="stat-grid"><div v-for="key in ['hp','atk','def','spd']" :key="key" class="stat-cell"><span>{{ statNames[key] }}</span><strong>{{ number(displayStat(key), key === 'hp' ? 0 : 1) }}</strong></div></div>
      <p class="muted detail-description">{{ leanDescriptions[template.lean] }} · 等级 {{ selected.level }}</p><p :class="selected.injury_stacks ? 'hurt-text' : 'muted'">{{ injuryText(selected) }}</p><p v-if="template?.production_specialty" class="notice-box">生产专长 · {{ resourceName(template.production_specialty,catalog) }}<br /><small>擅长对应资源的生产；选入队伍后，出发自动离岗，结算自动回岗。</small></p></section>
      <DiscipleTraining v-else-if="detailTab==='training'" :key="selected.id" :catalog="catalog" :preview="activeTraining" :loading="trainingLoading" :busy="store.busy" :read-only="readOnly" :pill-name="pillName" @upgrade="store.upgrade(selected.id)" @breakthrough="store.breakthrough(selected.id)" />
      <DiscipleEquipment v-else-if="detailTab==='equipment'" :key="selected.id" :disciple="selected" :read-only="readOnly" />
      <section v-else>
      <div v-if="skill(template.skill) || skill(template.passive)" class="skill-section"><div class="section-heading"><h4>道法典籍</h4><span class="badge">自动施展</span></div><SkillDetails v-if="skill(template.skill)" :skill="skill(template.skill)!" /><SkillDetails v-if="skill(template.passive)" :skill="skill(template.passive)!" passive /><p class="muted">主动就绪且有有效目标时施展，否则普攻。气血跨层保留，护盾与冷却每场重置。</p></div>
      <div v-if="bonds.length" class="bonds-section"><h4>同道羁绊</h4><div v-for="[id,bond] in bonds" :key="id" class="bond-row"><div class="section-heading"><strong>{{ bond.name }}</strong><span class="badge" :class="{'badge-muted':countBond(bond.members, !isBattleBond(bond))<(bond.requires ?? bond.members.length)}">{{ countBond(bond.members, !isBattleBond(bond)) }} / {{ bond.requires ?? bond.members.length }}</span></div><small class="bond-scope">{{ isBattleBond(bond) ? '战斗羁绊 · 按出征名单计数' : '值守羁绊 · 按值守编制计数' }}</small><p v-if="bond.description" class="muted">{{ bond.description }}</p><p class="muted">{{ bond.members.map(id=>catalog?.disciples[id]?.name ?? id).join(' · ') }}</p><span v-for="(effect,i) in bond.effects" :key="i" class="bond-effect">{{ effectText(effect) }}</span></div></div>
      <p v-if="!skill(template.skill) && !skill(template.passive) && !bonds.length" class="muted">暂未收录该弟子的道法与羁绊。</p></section>
      <div class="detail-actions"><button class="btn btn-primary" :disabled="store.busy || !!reason" @click="store.toggleParty(selected.id)"><GameIcon :name="selectedParty ? 'check' : 'plus'" />{{ selectedParty ? '移出出征阵容' : '加入出征阵容' }}</button><p v-if="reason" class="muted">{{ reason }}</p></div>
    </div>
  </PanelModal>
</template>
<style scoped>
.codex-heading{display:flex;align-items:center;gap:13px;margin-bottom:20px;padding:0 0 16px;border-bottom:1px solid #b8c3a4}
.codex-heading>svg{flex:none;width:45px;height:45px;padding:5px;color:#326c55;fill:#dfe8cf;stroke:currentColor;stroke-width:1.3;stroke-linejoin:miter}
.codex-heading>div{min-width:0}
.codex-heading h3{margin:0;font:25px 'SimSun',serif;color:#213f36;letter-spacing:2px}
.codex-heading p{margin:5px 0 0;font-size:11px;line-height:1.7;color:var(--muted)}
.roster-total{display:flex;align-items:baseline;gap:5px;flex:none;margin-left:auto;font-size:11px;color:#8c6844;white-space:nowrap}
.roster-total strong{font-size:28px;line-height:1;color:#326c55;font-weight:400;font-variant-numeric:tabular-nums}
.tabs{align-items:center}
.tabs>button{min-height:44px}
.tabs small{margin-left:6px;opacity:.7}
.search-input{margin-left:auto;width:150px;min-height:44px;font-size:12px;padding:6px 10px;background:#f8f3e1;border-color:#bdc5a7}
.formation-editor{position:relative;padding:0 13px;background:#e6ecd7;border:1px solid #b9c4a4;border-left:3px solid #76966e;margin-bottom:16px}
.formation-editor summary{display:flex;justify-content:space-between;align-items:center;gap:10px;min-height:44px;list-style:none;cursor:pointer}
.formation-editor summary::-webkit-details-marker{display:none}
.formation-editor summary:focus-visible{outline:2px solid var(--jade);outline-offset:2px}
.formation-title{font:17px 'SimSun',serif;color:#213f36}
.formation-title small{margin-left:8px;font:11px sans-serif;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.formation-toggle{display:flex;align-items:center;gap:5px;flex:none;font-size:11px;color:var(--muted)}
.formation-toggle svg{width:14px;height:14px}
.formation-collapse,.formation-editor[open] .formation-expand{display:none}
.formation-editor[open] .formation-collapse{display:inline}
.formation-editor[open] .formation-toggle svg{transform:rotate(90deg)}
.formation-content{padding-bottom:13px}
.formation-content .muted{margin:0 0 12px;font-size:11px;line-height:1.7}
.roster-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:9px;flex-wrap:wrap}
.roster-toolbar>.muted{font-size:11px}
.filter-list{display:flex;gap:5px;flex-wrap:wrap}
.filter-list button{min-width:39px;min-height:44px;border:1px solid #d0d2b8;padding:6px 11px;background:#eeeedc;color:var(--muted);font-size:12px}
.filter-list button.active{border-color:#326c55;background:#326c55;color:#f6f1df;box-shadow:inset 0 0 0 2px #ffffff16}
.filter-list button:focus-visible,.search-input:focus-visible,.tabs button:focus-visible,.detail-tabs button:focus-visible,.disciple-switch button:focus-visible{outline:2px solid var(--jade);outline-offset:2px}
.roster-hint{margin:0 0 14px;font-size:11px;color:var(--muted)}
.disciple-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;padding:2px}
.disciple-grid>.empty-state{grid-column:1 / -1}
.disciple-switch{display:flex;align-items:center;gap:4px}
.disciple-switch .btn{width:44px;height:44px;padding:10px;flex:none}
.disciple-switch>span{min-width:36px;text-align:center;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.previous-disciple{transform:rotate(180deg)}
.disciple-detail{min-width:0}
.detail-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;position:sticky;top:-24px;z-index:3;margin:-24px -26px 18px;padding:12px 26px;background:var(--surface);border-bottom:1px solid #bdc6a9}
.detail-tabs button{min-height:44px;padding:8px;border:1px solid transparent;background:transparent;color:var(--muted);font:15px 'SimSun',serif}
.detail-tabs button.active{border-color:#8fa685;border-bottom:3px solid #326c55;background:#e0e8cf;color:#213f36}
.detail-title{position:relative;isolation:isolate;min-height:204px;display:flex;align-items:center;margin-bottom:18px;padding:18px;border:1px solid #bec5a7;border-bottom:3px solid #8c6844;background:#e7ecd9;overflow:hidden}
.detail-title::before{content:'';position:absolute;inset:5px;pointer-events:none;border:1px solid #b4c0a1}
.identity-copy{position:relative;max-width:calc(100% - 140px);z-index:2}
.identity-landscape{position:absolute;inset:0;width:100%;height:100%;color:#8da57f;stroke:currentColor;stroke-width:1;opacity:.5}
.identity-title{font-size:11px;color:#8c6844;line-height:1.6}
.detail-title h3{font:32px/1.3 'SimSun',serif;margin:8px 0 10px;letter-spacing:2px;color:#213f36;overflow-wrap:anywhere}
.identity-tags{display:flex;flex-wrap:wrap;gap:5px}
.identity-tags>span{padding:2px 6px;font-size:10px;color:#326c55;border:1px solid #a7b797;background:#f6f1dfb8}
.identity-tags>span:first-child{color:#8c6844;border-color:#c7b78d}
.identity-level{display:flex;align-items:baseline;flex-wrap:wrap;gap:5px;margin:13px 0 0;font-size:11px;color:#536b50}
.identity-level strong{font-size:20px;font-variant-numeric:tabular-nums;font-weight:500;color:#213f36}
.identity-level>span{margin-left:8px;font-size:10px}
.detail-portrait{position:absolute;top:0;right:-2px;width:185px;height:100%;object-fit:cover;object-position:center 17%;mask-image:linear-gradient(to bottom,#000 84%,transparent)}
.attribute-heading{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:9px;font-size:11px;color:var(--muted)}
.attribute-heading>span:last-child{color:#326c55}
.disciple-detail .stat-grid{gap:0;border-block:1px solid #d3c8aa}
.disciple-detail .stat-cell{padding:12px 9px;background:transparent;border-top:0;border-right:1px solid #d3c8aa}
.disciple-detail .stat-cell:last-child{border-right:0}
.stat-cell strong{font-size:21px;color:#213f36;font-variant-numeric:tabular-nums}
.stat-cell>span{font-size:11px}
.detail-description{margin:14px 0 4px;font-size:12px;line-height:1.8}
.hurt-text{color:var(--danger);font-size:11px;margin-bottom:15px}
.skill-section,.bonds-section{padding-top:0;margin-top:0}
.skill-section h4,.bonds-section h4{margin:0 0 8px;font:18px 'SimSun',serif;color:#213f36}
.skill-section .section-heading{margin-bottom:10px}
.bonds-section{margin-top:20px;padding-top:16px;border-top:1px solid #c7ccb0}
.bond-row{padding:11px 12px;border-left:2px solid #95ac87;background:#edf0df;margin-top:10px}
.bond-row .section-heading{margin-bottom:4px}
.bond-row strong{font:15px 'SimSun',serif;color:#213f36}
.bond-scope{display:block;font-size:10px;color:var(--gold);margin-top:5px}
.bond-row p{margin:4px 0;font-size:11px;line-height:1.8}
.bond-effect{font-size:11px;line-height:1.8;color:var(--jade);margin-right:8px}
.detail-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px;padding-top:14px;border-top:1px solid #c7ccb0}
.detail-actions>.btn-primary{width:100%;min-height:44px}
.detail-actions>p{width:100%;margin:0}
.recruit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.recruit-card{position:relative;display:flex;gap:16px;padding:12px;background:#f1efdd;border:1px solid #bcc5a6;border-left:3px solid #8da77d;overflow:hidden}
.recruit-card>img{width:100px;height:145px;object-fit:cover;background:#dfe8cf;border:1px solid #bdc6a6;object-position:center 15%}
.recruit-card>div{flex:1;min-width:0;align-self:center}
.recruit-card .eyebrow{font-size:10px;color:#8c6844;letter-spacing:0}
.recruit-card h3{font:22px/1.3 'SimSun',serif;color:#213f36;margin:8px 0}
.recruit-card h3 small{display:block;font:11px system-ui;color:var(--muted);margin-top:5px}
.recruit-card p{font-size:11px;line-height:1.8;margin-bottom:12px}
.recruit-card .btn{min-height:44px;font-size:11px;white-space:normal;line-height:1.6}
.recruit-card .badge{display:inline-block;margin:0 6px 6px 0}
@media(max-width:820px){.recruit-grid{grid-template-columns:1fr}}
@media(max-width:640px){
  .codex-heading{gap:9px;margin-bottom:15px;padding-bottom:13px}
  .codex-heading>svg{width:37px;height:37px;padding:3px}
  .codex-heading h3{font-size:22px}
  .codex-heading p{font-size:10px}
  .roster-total{flex-direction:column;gap:3px;align-items:center;font-size:10px}
  .roster-total strong{font-size:25px}
  .tabs{flex-wrap:wrap}
  .tabs button{padding-inline:12px}
  .search-input{width:100%;margin:6px 0 0}
  .formation-editor{padding:0 10px}
  .formation-editor .muted{font-size:10px}
  .roster-toolbar{align-items:flex-start;flex-direction:column}
  .filter-list{gap:4px}
  .filter-list button{min-width:33px;padding-inline:8px;font-size:11px}
  .disciple-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
  .detail-tabs{top:-18px;margin:-18px -14px 16px;padding:10px 14px;gap:3px}
  .detail-tabs button{font-size:14px;padding-inline:5px}
  .disciple-switch{gap:0}
  .disciple-switch>span{min-width:30px;font-size:11px}
  .detail-title{padding:15px 13px;min-height:190px}
  .identity-copy{max-width:calc(100% - 112px)}
  .detail-title h3{font-size:29px;letter-spacing:1px}
  .detail-portrait{width:153px;right:-10px}
  .identity-level{gap:4px}
  .identity-level>span{margin-left:3px}
  .identity-title{font-size:10px}
  .disciple-detail .stat-cell{padding:10px 6px}
  .stat-cell strong{font-size:18px}
  .recruit-card{gap:12px;padding:10px}
  .recruit-card>img{width:84px;height:134px}
  .recruit-card h3{font-size:21px}
}
</style>
