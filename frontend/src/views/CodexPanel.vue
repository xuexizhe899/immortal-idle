<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import DiscipleCard from '../components/game/DiscipleCard.vue'
import DiscipleEquipment from '../components/game/DiscipleEquipment.vue'
import DiscipleTraining from '../components/game/DiscipleTraining.vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import SkillDetails from '../components/game/SkillDetails.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { discipleImage } from '../presentation/assetPaths'
import { effectText,injuryText,leanNames,leanDescriptions,rarityNames,statNames,type DisplayCatalog,type DisplaySkill } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
const props=defineProps<{readOnly?:boolean}>()
const store = useGameStore()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const tab = ref('roster'); const filter = ref('all'); const selectedId = ref(''); const search = ref('')
const onDuty = computed(() => new Set(store.state?.duty_slots?.map(s => s.disciple_id) ?? []))
const roster = computed(() => store.disciples.filter(d => { const template=catalog.value?.disciples[d.template_id]; return (!search.value || template?.name.includes(search.value)) && (filter.value==='all' || (filter.value==='hurt' ? d.injury_stacks>0 : filter.value==='duty' ? onDuty.value.has(d.id) : template?.lean===filter.value)) }))
const selected = computed(() => store.disciples.find(d => d.id === selectedId.value) ?? roster.value[0])
const template = computed(() => selected.value ? catalog.value?.disciples[selected.value.template_id] : null)
const full = computed(() => store.party.length >= (catalog.value?.rules.max_party ?? 6))
const selectedParty = computed(() => !!selected.value && store.party.includes(selected.value.id))
const reason = computed(() => props.readOnly ? '出征期间阵容已锁定' : !selected.value ? '请选择弟子' : selected.value.busy ? '正在出征' : onDuty.value.has(selected.value.id) ? '请先在值守面板中下岗' : full.value && !selectedParty.value ? '出征队伍已满' : '')
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
function goTrain(templateId: string) {
  const disciple = store.disciples.find(d => d.template_id === templateId)
  if (!disciple) { store.notice = '该弟子暂不可培养。'; return }
  tab.value = 'roster'
  filter.value = 'all'
  search.value = ''
  selectedId.value = disciple.id
  nextTick(scrollToRoster)
}
watch(roster, list=>{if (!list.some(d=>d.id===selectedId.value)) selectedId.value=list[0]?.id ?? ''},{immediate:true})
watch([() => selected.value?.id, () => store.revision], ([id]) => {
  if (id) void store.loadTraining(id)
}, { immediate: true })
</script>
<template>
  <div class="tabs" role="tablist" aria-label="弟子管理"><button :class="{active:tab==='roster'}" role="tab" :aria-selected="tab==='roster'" @click="tab='roster'">门下弟子 <small>{{ store.disciples.length }}</small></button><button :class="{active:tab==='recruit'}" role="tab" :aria-selected="tab==='recruit'" @click="tab='recruit'">招贤纳士</button><input v-model="search" aria-label="查找弟子" placeholder="查找弟子" class="search-input" /></div>
  <template v-if="tab==='roster'">
    <div class="formation-editor"><div class="section-heading"><h4>出征编队</h4><span class="muted">顺序决定同身法出手与目标优先级</span></div><PartyStrip compact reorder @edit="scrollToRoster" /></div><div id="disciple-roster" class="roster-toolbar"><div class="filter-list"><button v-for="(label,id) in {all:'全部',attack:'攻',defense:'防',support:'辅',craft:'炼',duty:'值守',hurt:'受伤'}" :key="id" :class="{active:filter===id}" @click="filter=id">{{ label }}</button></div><span class="muted">出征阵容 {{ store.party.length }} / {{ catalog?.rules.max_party ?? 6 }}</span></div>
    <div class="roster-layout"><div class="disciple-grid"><DiscipleCard v-for="d in roster" :key="d.id" :disciple="d" :name="catalog?.disciples[d.template_id]?.name ?? d.template_id" :selected="store.party.includes(d.id)" :active="selected?.id===d.id" :asset="discipleImage(d.template_id,catalog)" :lean="catalog?.disciples[d.template_id]?.lean" :rarity="catalog?.disciples[d.template_id]?.rarity" :duty="onDuty.has(d.id)" @toggle="selectedId=d.id" /><div v-if="!roster.length" class="empty-state"><strong>暂未寻得弟子</strong>调整筛选，或前往招贤纳士。</div></div>
    <aside v-if="selected && template" class="disciple-detail"><div class="detail-title"><div><span class="eyebrow">{{ template.title }} · {{ rarityNames[template.rarity] }}</span><h3>{{ template.name }}</h3><span class="badge">{{ leanNames[template.lean] }} · 境界 {{ selected.realm }}</span></div><img :src="discipleImage(selected.template_id,catalog)" :alt="template.name" class="detail-portrait pixel-art" /></div>
      <p class="muted" style="margin-bottom:8px">人物基础属性</p><div class="stat-grid"><div v-for="key in ['hp','atk','def','spd']" :key="key" class="stat-cell"><span>{{ statNames[key] }}</span><strong>{{ number(displayStat(key), key === 'hp' ? 0 : 1) }}</strong></div></div>
      <p class="muted detail-description">{{ leanDescriptions[template.lean] }} · 等级 {{ selected.level }}</p><p :class="selected.injury_stacks ? 'hurt-text' : 'muted'">{{ injuryText(selected) }}</p><DiscipleTraining :preview="activeTraining" :loading="trainingLoading" :busy="store.busy" :read-only="readOnly" :pill-name="pillName" @upgrade="store.upgrade(selected.id)" @breakthrough="store.breakthrough(selected.id)" /><DiscipleEquipment :disciple="selected" :read-only="readOnly" />
      <div v-if="skill(template.skill) || skill(template.passive)" class="skill-section"><div class="section-heading"><h4>道法典籍</h4><span class="badge">自动施展</span></div><SkillDetails v-if="skill(template.skill)" :skill="skill(template.skill)!" /><SkillDetails v-if="skill(template.passive)" :skill="skill(template.passive)!" passive /><p class="muted">主动就绪且有有效目标时施展，否则普攻。气血跨层保留，护盾与冷却每场重置。</p></div>
      <div v-if="bonds.length" class="bonds-section"><h4>同道羁绊</h4><div v-for="[id,bond] in bonds" :key="id" class="bond-row"><div class="section-heading"><strong>{{ bond.name }}</strong><span class="badge" :class="{'badge-muted':countBond(bond.members, !isBattleBond(bond))<(bond.requires ?? bond.members.length)}">{{ countBond(bond.members, !isBattleBond(bond)) }} / {{ bond.requires ?? bond.members.length }}</span></div><small class="bond-scope">{{ isBattleBond(bond) ? '战斗羁绊 · 按出征名单计数' : '值守羁绊 · 按值守编制计数' }}</small><p v-if="bond.description" class="muted">{{ bond.description }}</p><p class="muted">{{ bond.members.map(id=>catalog?.disciples[id]?.name ?? id).join(' · ') }}</p><span v-for="(effect,i) in bond.effects" :key="i" class="bond-effect">{{ effectText(effect) }}</span></div></div>
      <div class="detail-actions"><button class="btn btn-primary" :disabled="store.busy || !!reason" @click="store.toggleParty(selected.id)"><GameIcon :name="selectedParty ? 'check' : 'plus'" />{{ selectedParty ? '移出出征阵容' : '加入出征阵容' }}</button><p v-if="reason" class="muted">{{ reason }}</p></div>
    </aside></div>
  </template>
  <template v-else><div class="section-heading"><p class="muted">以声望访贤，邀同道入山。</p><span class="badge badge-gold">声望 {{ number(store.resources?.reputation) }}</span></div><div class="recruit-grid"><article v-for="[id,d] in recruitables" :key="id" class="recruit-card"><img :src="discipleImage(id,catalog)" :alt="d.name" class="pixel-art" loading="lazy" decoding="async" /><div><span class="eyebrow">{{ rarityNames[d.rarity] }} · {{ leanNames[d.lean] }}</span><h3>{{ d.name }} <small>{{ d.title }}</small></h3><p class="muted">{{ leanDescriptions[d.lean] }}</p><template v-if="owned.has(id)"><span class="badge">已拥有</span><button class="btn btn-small" :disabled="readOnly || store.busy" @click="goTrain(id)">前往培养</button></template><button v-else class="btn btn-small btn-primary" :disabled="readOnly || store.busy || (store.resources?.reputation ?? 0)<(d.unlock_cost?.reputation??0)" @click="store.recruit(id)">邀入宗门 · {{ number(d.unlock_cost?.reputation??0) }} 声望</button></div></article></div></template>
</template>
<style scoped>
.formation-editor{padding:12px;background:#e6e8d7;border:1px solid #c9c5a8;margin-bottom:18px}.formation-editor h4{margin:0;font-size:14px}.formation-editor .section-heading{gap:8px}.formation-editor .muted{font-size:10px}.bond-scope{display:block;font-size:9px;color:var(--gold);margin-top:5px}.tabs{align-items:center}.tabs small{margin-left:6px;opacity:.7}.search-input{margin-left:auto;width:150px;min-height:34px;font-size:11px;padding:6px 10px}.roster-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:18px}.filter-list{display:flex;gap:3px;flex-wrap:wrap}.filter-list button{border:1px solid transparent;padding:4px 10px;background:transparent;color:var(--muted);font-size:11px;min-height:32px}.filter-list button.active{border-color:#a9b49c;color:var(--jade);background:#e4ead9}.roster-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:26px;align-items:start}.disciple-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(105px,1fr));gap:10px;max-height:580px;overflow-y:auto;padding:2px}.disciple-detail{padding:18px;background:#eee9d9;border:1px solid #d3c8aa;min-width:0}.detail-title{position:relative;min-height:155px;display:flex;align-items:center;margin-bottom:12px}.detail-title>div{position:relative;z-index:1}.detail-title h3{font-size:28px;margin:8px 0}.detail-title .eyebrow{font-size:8px;max-width:140px}.detail-portrait{position:absolute;right:-8px;top:-10px;width:145px;height:174px;object-fit:cover;object-position:center 16%;mask-image:linear-gradient(to bottom,#000 75%,transparent)}.stat-cell strong{font-size:17px}.detail-description{margin:14px 0 4px}.hurt-text{color:var(--danger);font-size:11px;margin-bottom:15px}.skill-section,.bonds-section{padding-top:16px;border-top:1px solid #d3c8aa;margin-top:16px}.skill-section h4,.bonds-section h4{margin:0 0 8px;font-size:14px}.skill-section .section-heading{margin-bottom:10px}.bond-row{margin-top:9px}.bond-row .section-heading{margin-bottom:4px}.bond-row strong{font-size:12px}.bond-row p{margin:4px 0}.bond-effect{font-size:11px;color:var(--jade);margin-right:8px}.detail-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.detail-actions>.btn-primary{width:100%}.detail-actions>p{width:100%;margin:0}.recruit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.recruit-card{display:flex;gap:16px;background:#eee9d8;border:1px solid #d3c8aa;padding:12px}.recruit-card>img{width:92px;height:130px;object-fit:cover;object-position:top}.recruit-card>div{flex:1;min-width:0}.recruit-card .eyebrow{font-size:8px}.recruit-card h3{font-size:19px;margin:5px 0}.recruit-card h3 small{font-size:10px;color:var(--muted);font-family:system-ui}.recruit-card p{font-size:10px;margin-bottom:12px}.recruit-card .btn{font-size:10px}.recruit-card .badge{display:inline-block;margin:0 6px 6px 0}
@media(max-width:820px){.roster-layout{grid-template-columns:minmax(0,1fr) 290px;gap:16px}.recruit-grid{grid-template-columns:1fr}}
@media(max-width:640px){.tabs{flex-wrap:wrap}.tabs button{padding-inline:12px}.search-input{width:100%;margin:6px 0 0}.roster-toolbar{align-items:flex-start;flex-direction:column}.roster-layout{grid-template-columns:1fr;gap:18px}.disciple-grid{grid-template-columns:repeat(3,minmax(0,1fr));max-height:300px;gap:7px}.disciple-detail{padding:16px}.detail-title{min-height:140px}.detail-portrait{right:15px}.recruit-card{gap:12px;padding:10px}.recruit-card>img{width:80px;height:120px}.recruit-card h3 small{display:block;margin-top:3px}.recruit-card .btn{font-size:11px}}
</style>
