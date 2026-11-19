<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { GearView } from '../api/client'
import GearIcon from '../components/game/GearIcon.vue'
import { equipmentAffixText, equipmentComparison, equipmentPercent, equipmentSlotNames, equipmentSlots, equipmentStats, smeltBlockReason } from '../presentation/equipment'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

const props = defineProps<{ readOnly?: boolean }>()
const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const slotFilter = ref('all')
const ownerFilter = ref('all')
const search = ref('')
const selectedId = ref('')
const detailTab = ref('upgrade')
const confirmSmelt = ref(false)
const loading = ref(false)
const loadFailed = ref(false)
let loadRequest = 0
const slots = computed(() => store.gearRules?.slots ?? equipmentSlotNames)
const material = computed(() => store.gearRules?.material ?? 'lian_qi_jing_cui')
const materialName = computed(() => store.gearRules?.material_name ?? '炼器精粹')
const filtered = computed(() => store.gearList.filter(item =>
  (slotFilter.value === 'all' || item.slot === slotFilter.value)
  && (ownerFilter.value === 'all' || (ownerFilter.value === 'bag' ? !item.equipped_by : ownerFilter.value === 'pending' ? !!item.pending_affix : !!item.equipped_by))
  && (!search.value || item.name.includes(search.value.trim())),
))
const selected = computed(() => store.gearList.find(item => item.id === selectedId.value))
const comparison = computed(() => selected.value ? equipmentComparison(selected.value.stats, selected.value.upgrade_stats) : [])
const upgradeReason = computed(() => props.readOnly ? '出征结束后可强化装备' : selected.value?.upgrade_reason ?? '')
const reforgeReason = computed(() => props.readOnly ? '出征结束后可洗练装备' : selected.value?.reforge_reason ?? '')
const resolveReason = computed(() => props.readOnly ? '出征结束后可选择洗练结果' : selected.value?.resolve_reason ?? '')
const smeltReason = computed(() => selected.value ? smeltBlockReason(selected.value, props.readOnly) : '')

async function refresh(silent = false) {
  const request = ++loadRequest
  if (!silent) loading.value = true
  try {
    await store.loadEquipment(silent)
    if (request === loadRequest) loadFailed.value = !store.gearRules
  } catch {
    if (request === loadRequest) loadFailed.value = true
  } finally {
    if (request === loadRequest) loading.value = false
  }
}
watch(() => store.slotId, () => { void refresh() }, { immediate: true })
watch(() => store.revision, () => { void refresh(true) })
watch(filtered, items => {
  if (!items.some(item => item.id === selectedId.value)) selectedId.value = items[0]?.id ?? ''
}, { immediate: true })
watch(selectedId, () => { confirmSmelt.value = false })
watch(() => selected.value?.pending_affix, pending => { if (pending) detailTab.value = 'reforge' }, { immediate: true })
function held(id: string) { return store.state?.inventory[id] ?? 0 }
function ownerName(id: string | null) {
  const disciple = store.disciples.find(item => item.id === id)
  return disciple ? store.catalog?.disciples[disciple.template_id]?.name ?? disciple.template_id : '行囊'
}
function currentAffix(item: GearView) { return equipmentAffixText(item.affix, item.affix_value, item.affix_grade) }
async function smelt() {
  if (!selected.value || smeltReason.value || !confirmSmelt.value || store.busy) return
  await store.equipmentAction('smelt', selected.value.id)
  confirmSmelt.value = false
}
</script>

<template>
  <section class="equipment-workshop" aria-label="个人装备提升">
    <div class="equipment-intro"><div><h3>个人装备</h3><p>武器、盔甲、靴子与戒指，增益只属于穿戴它的弟子。</p></div><div class="material-stock"><span>{{ materialName }}</span><strong>{{ number(held(material)) }}</strong></div></div>
    <p v-if="readOnly" class="notice-box">出征尚未结算，可查阅装备；结算后可强化、洗练和熔炼。</p>
    <div class="equipment-toolbar"><div class="slot-filters" aria-label="筛选装备部位"><button :class="{active:slotFilter==='all'}" :aria-pressed="slotFilter==='all'" @click="slotFilter='all'">全部</button><button v-for="slot in equipmentSlots" :key="slot" :class="{active:slotFilter===slot}" :aria-pressed="slotFilter===slot" @click="slotFilter=slot">{{ slots[slot]??equipmentSlotNames[slot] }}</button></div><div class="equipment-search"><select v-model="ownerFilter" aria-label="筛选装备归属"><option value="all">全部归属</option><option value="bag">行囊中</option><option value="equipped">已穿戴</option><option value="pending">待选洗练</option></select><input v-model="search" aria-label="查找装备" placeholder="查找装备" /><button class="btn btn-small" :disabled="store.busy||loading" @click="refresh()">{{ loading?'查阅中…':'刷新' }}</button></div></div>
    <p v-if="loadFailed" class="error-box" role="alert">装备资料暂未取到，请刷新后重试。</p>
    <p v-if="loading&&!store.gearList.length" class="notice-box" role="status">正在查阅装备与材料……</p>
    <div v-else-if="!store.gearList.length&&!loadFailed" class="empty-state"><strong>行囊中还没有普通装备</strong><p>在世界地图探索秘境、挑战首领，结算后即可带回装备。</p><button class="btn btn-small" @click="emit('open','codex')">查看弟子装备位</button></div>
    <div v-else class="equipment-layout">
      <div class="gear-list" aria-label="选择要提升的装备"><p class="list-count">{{ filtered.length }} / {{ store.gearList.length }} 件装备</p><button v-for="item in filtered" :key="item.id" :class="{active:selectedId===item.id,pending:!!item.pending_affix}" :aria-pressed="selectedId===item.id" @click="selectedId=item.id"><GearIcon :slot="item.slot" :size="34" /><span><strong>{{ item.name }} <small>+{{ item.level }}</small></strong><small>{{ item.tier }} 阶 · {{ slots[item.slot]??item.slot }} · {{ item.equipped_by?ownerName(item.equipped_by):'行囊中' }}</small><em v-if="item.pending_affix">待选择洗练结果</em><em v-else-if="item.locked" class="locked-label">已锁定</em></span></button><p v-if="!filtered.length" class="filter-empty">没有符合条件的装备，可切换部位或归属。</p></div>
      <article v-if="selected" class="gear-detail">
        <header class="gear-detail-head"><GearIcon :slot="selected.slot" :size="54" /><div><span>{{ selected.tier }} 阶 {{ slots[selected.slot]??selected.slot }}</span><h4>{{ selected.name }} <small>+{{ selected.level }}</small></h4><p>{{ selected.equipped_by?'穿戴者：'+ownerName(selected.equipped_by):'位于行囊中' }}</p></div><button class="btn btn-small" :disabled="store.busy||readOnly||!!selected.lock_reason" :aria-pressed="selected.locked" @click="store.equipmentAction('lock',selected.id,{locked:!selected.locked})">{{ selected.locked?'解除锁定':'锁定装备' }}</button></header>
        <p v-if="selected.lock_reason" class="equipment-reason">{{ selected.lock_reason }}</p>
        <div class="gear-stats"><span v-for="stat in equipmentStats(selected.stats)" :key="stat.stat">{{ stat.name }} <strong>{{ stat.text }}</strong></span></div>
        <p class="affix-description">副属性：{{ currentAffix(selected) }}</p>
        <p v-if="selected.source==='legacy'" class="legacy-note">由旧器具转化，穿戴后为对应弟子提供增益。</p>
        <div class="detail-tabs" aria-label="选择装备操作"><button :class="{active:detailTab==='upgrade'}" :aria-pressed="detailTab==='upgrade'" @click="detailTab='upgrade'">强化</button><button :class="{active:detailTab==='reforge'}" :aria-pressed="detailTab==='reforge'" @click="detailTab='reforge'">洗练<span v-if="selected.pending_affix" class="pending-dot"></span></button><button :class="{active:detailTab==='smelt'}" :aria-pressed="detailTab==='smelt'" @click="detailTab='smelt'">熔炼</button></div>
        <section v-if="detailTab==='upgrade'" class="equipment-action">
          <h5>强化 {{ selected.level }} → {{ Math.min(selected.level+1,selected.max_level) }} 级</h5><p>提升主属性，副属性与穿戴归属保留。当前炼器设施允许强化至 {{ selected.max_level }} 级。</p>
          <table v-if="selected.level<selected.max_level" class="comparison-table"><caption>装备增益变化</caption><thead><tr><th scope="col">属性</th><th scope="col">当前</th><th scope="col">强化后</th></tr></thead><tbody><tr v-for="row in comparison" :key="row.stat"><th scope="row">{{ row.name }}</th><td>{{ equipmentPercent(row.current) }}</td><td :class="{improved:row.delta>0}">{{ equipmentPercent(row.candidate) }}</td></tr></tbody></table>
          <div v-if="selected.level<selected.max_level" class="equipment-costs"><strong>本次消耗</strong><span v-for="(amount,id) in selected.upgrade_costs" :key="id" :class="{missing:held(id)<amount}">{{ resourceName(id,store.catalog) }} <b>{{ held(id) }} / {{ amount }}</b></span></div>
          <p v-if="upgradeReason" class="equipment-reason">{{ upgradeReason }}</p><button class="btn btn-primary action-button" :disabled="store.busy||!!upgradeReason||!selected.upgradeable" @click="store.equipmentAction('upgrade',selected.id)">{{ store.busy?'正在确认…':'强化这件装备' }}</button>
        </section>
        <section v-else-if="detailTab==='reforge'" class="equipment-action">
          <h5>{{ selected.pending_affix?'选择本次洗练结果':'重炼副属性' }}</h5><p>重抽副属性与强度档位，主属性和强化等级保留。可在看到结果后保留旧属性。</p>
          <div v-if="selected.pending_affix" class="reforge-result"><article><span>现有副属性</span><strong>{{ currentAffix(selected) }}</strong></article><article class="new-affix"><span>本次新结果</span><strong>{{ equipmentAffixText(selected.pending_affix.stat,selected.pending_affix.value,selected.pending_affix.grade) }}</strong></article><p>本次材料已消耗，未确认前仍使用原副属性；关闭面板后也可继续选择。</p><p v-if="resolveReason" class="equipment-reason">{{ resolveReason }}</p><div><button class="btn" :disabled="store.busy||!!resolveReason" @click="store.equipmentAction('resolve',selected.id,{keep:true})">保留原属性</button><button class="btn btn-primary" :disabled="store.busy||!!resolveReason" @click="store.equipmentAction('resolve',selected.id,{keep:false})">采用新属性</button></div></div>
          <template v-else><div class="equipment-costs"><strong>本次消耗</strong><span v-for="(amount,id) in selected.reforge_costs" :key="id" :class="{missing:held(id)<amount}">{{ resourceName(id,store.catalog) }} <b>{{ held(id) }} / {{ amount }}</b></span></div><p v-if="reforgeReason" class="equipment-reason">{{ reforgeReason }}</p><button class="btn btn-primary action-button" :disabled="store.busy||!!reforgeReason" @click="store.equipmentAction('reforge',selected.id)">{{ store.busy?'正在确认…':'消耗材料，生成洗练结果' }}</button></template>
        </section>
        <section v-else class="equipment-action smelt-action">
          <h5>将装备熔炼为材料</h5><p>装备本体转为强化材料；强化与可追溯旧锻造投入返还 80%，洗练消耗不退。实际所得如下。</p>
          <div class="equipment-costs returns"><strong>熔炼后获得</strong><span v-for="(amount,id) in selected.smelt_returns" :key="id">{{ resourceName(id,store.catalog) }} <b>+{{ number(amount) }}</b></span></div>
          <p v-if="smeltReason" class="equipment-reason">{{ smeltReason }}</p><p v-if="selected.locked" class="action-note">锁定用于防止误熔炼；可先在装备名称旁解除锁定。</p>
          <div v-if="confirmSmelt&&!smeltReason" class="smelt-confirm" role="alert"><strong>确认熔炼「{{ selected.name }} +{{ selected.level }}」？</strong><p>这件装备将消失，上方所列材料会收入行囊。</p><button class="btn btn-danger" :disabled="store.busy||!!smeltReason" @click="smelt">确认熔炼</button><button class="btn btn-quiet" :disabled="store.busy" @click="confirmSmelt=false">保留装备</button></div>
          <button v-else class="btn btn-danger action-button" :disabled="store.busy||!!smeltReason" @click="confirmSmelt=true">熔炼这件装备</button>
        </section>
      </article>
    </div>
  </section>
</template>

<style scoped>
.equipment-intro{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:16px 0 18px;border-bottom:1px solid var(--border)}.equipment-intro h3{font-size:23px;margin:0 0 6px}.equipment-intro p{font-size:12px;color:var(--muted);margin:0;max-width:42em}.material-stock{flex:none;text-align:right;color:var(--jade)}.material-stock span{display:block;font-size:11px;color:var(--muted)}.material-stock strong{font:25px 'SimSun',serif;font-variant-numeric:tabular-nums}.equipment-workshop>.notice-box{margin-top:14px}.equipment-toolbar{margin:16px 0;display:flex;flex-direction:column;gap:10px}.slot-filters{display:flex;flex-wrap:wrap;gap:5px}.slot-filters button,.detail-tabs button{border:1px solid transparent;background:transparent;color:var(--muted);padding:7px 13px;min-height:36px;font-size:12px}.slot-filters button.active,.detail-tabs button.active{border-color:#9caf8b;background:#e0e7d1;color:var(--jade)}.equipment-search{display:flex;gap:7px}.equipment-search select,.equipment-search input{font-size:11px;min-height:36px;padding:6px 9px}.equipment-search select{width:115px}.equipment-search input{width:0;flex:1}.equipment-layout{display:grid;grid-template-columns:minmax(150px,.75fr) minmax(0,1.25fr);gap:15px;align-items:start}.gear-list{max-height:560px;overflow-y:auto;overscroll-behavior:contain;padding:1px}.list-count{font-size:10px;color:var(--muted);margin:0 0 8px}.gear-list>button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:10px 8px;margin-bottom:6px;background:#eee9d7;border:1px solid #c9c4a7}.gear-list>button.active{border-color:var(--jade);background:#dfe7d1;box-shadow:inset 3px 0 var(--jade)}.gear-list>button.pending{border-right:3px solid var(--gold)}.gear-list>button>span{min-width:0}.gear-list strong{display:block;font:14px 'SimSun',serif;overflow-wrap:anywhere}.gear-list strong>small{font-size:12px;color:var(--gold)}.gear-list span>small{display:block;font-size:9px;color:var(--muted);line-height:1.7;margin-top:4px}.gear-list em{display:block;margin-top:4px;font-size:9px;font-style:normal;color:#9b702e}.gear-list em.locked-label{color:#6e7f62}.filter-empty{padding:15px 8px;font-size:12px;line-height:1.8;color:var(--muted)}.gear-detail{min-width:0;padding:17px;background:#f5efdd;border:1px solid #c5b895}.gear-detail-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.gear-detail-head>div{flex:1;min-width:100px}.gear-detail-head>div>span{font-size:10px;color:var(--gold)}.gear-detail-head h4{font-size:21px;margin:4px 0;overflow-wrap:anywhere}.gear-detail-head h4 small{font-size:15px;color:var(--gold)}.gear-detail-head p{font-size:10px;color:var(--muted);margin:0}.gear-detail-head>.btn{margin-left:auto;font-size:10px}.gear-stats{display:flex;gap:5px 14px;flex-wrap:wrap;margin:15px 0 8px;padding:12px 0;border-block:1px solid #d8cfb5;font-size:11px;color:var(--muted)}.gear-stats strong{font-weight:500;color:var(--jade);font-variant-numeric:tabular-nums}.affix-description,.legacy-note{font-size:10px;color:var(--muted);line-height:1.8;margin:6px 0}.legacy-note{color:#8b794d}.detail-tabs{display:flex;gap:4px;margin:18px 0 14px;padding-bottom:7px;border-bottom:1px solid var(--border)}.detail-tabs button{position:relative;flex:1;padding-inline:8px}.pending-dot{display:inline-block;width:5px;height:5px;vertical-align:middle;background:var(--gold);margin-left:5px;transform:rotate(45deg)}.equipment-action h5{font:18px 'SimSun',serif;margin:0 0 8px;color:var(--jade)}.equipment-action>p{font-size:11px;color:var(--muted);line-height:1.8;margin:6px 0 12px}.comparison-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:11px;font-variant-numeric:tabular-nums}.comparison-table caption{text-align:left;font-size:10px;color:var(--muted);padding-bottom:6px}.comparison-table th,.comparison-table td{text-align:right;border-bottom:1px solid #d9d0b7;padding:7px 5px;font-weight:400}.comparison-table tr>:first-child{text-align:left;color:var(--muted)}.comparison-table thead th{font-size:10px;color:var(--muted)}.comparison-table td.improved{color:var(--jade);font-weight:600}.equipment-costs{display:flex;flex-direction:column;gap:7px;padding:11px 0;border-block:1px solid #d8cfb5;font-size:11px;margin:12px 0}.equipment-costs>strong{font-weight:500;color:var(--muted);font-size:10px}.equipment-costs>span{display:flex;justify-content:space-between;gap:8px}.equipment-costs b{font-weight:500;color:var(--jade);font-variant-numeric:tabular-nums}.equipment-costs .missing,.equipment-costs .missing b{color:var(--danger)}.equipment-reason,.equipment-action>p.equipment-reason{color:var(--danger);font-size:11px;line-height:1.8;margin:10px 0}.action-button{width:100%;margin-top:8px;white-space:normal;min-height:42px}.reforge-result article{padding:12px;border:1px solid #c7c7a9;background:#ecead7;margin-top:9px}.reforge-result article span{display:block;font-size:10px;color:var(--muted);margin-bottom:5px}.reforge-result article strong{font-size:12px;font-weight:500;color:var(--jade)}.reforge-result .new-affix{border-color:#bfaa73;background:#f4e9ce}.reforge-result>p{font-size:11px;line-height:1.8;color:var(--muted);margin:12px 0}.reforge-result>div{display:flex;gap:7px;flex-wrap:wrap}.reforge-result .btn{flex:1;font-size:11px;padding-inline:9px}.smelt-confirm{padding:12px;background:#f3e5d5;border:1px solid #c79578;margin-top:13px}.smelt-confirm>strong{font-size:12px;color:var(--danger);overflow-wrap:anywhere}.smelt-confirm p{font-size:11px;color:var(--muted);line-height:1.8;margin:8px 0}.smelt-confirm .btn{font-size:11px;margin-top:5px}.equipment-action>p.action-note{font-size:10px}.equipment-workshop .empty-state p{font-size:12px;line-height:1.9;margin:9px 0 15px}
@media(max-width:640px){.equipment-intro{align-items:flex-start;padding-top:6px}.equipment-intro h3{font-size:21px}.equipment-intro p{font-size:12px;line-height:1.8}.material-stock strong{font-size:22px}.equipment-layout{grid-template-columns:1fr;gap:12px}.gear-list{max-height:245px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gear-list .list-count,.gear-list .filter-empty{grid-column:1 / -1}.gear-list>button{margin:0;padding:9px 6px;align-items:flex-start;gap:5px}.gear-list>button>.gear-icon{width:28px;height:30px}.gear-list strong{font-size:13px;line-height:1.5}.gear-list span>small,.gear-list em{font-size:10px}.gear-detail{padding:14px}.equipment-search{flex-wrap:wrap}.equipment-search select{width:110px}.equipment-search input{min-width:80px}.equipment-search select,.equipment-search input,.equipment-search .btn,.slot-filters button,.detail-tabs button{min-height:44px}.slot-filters button{padding-inline:12px}.gear-detail-head h4{font-size:22px}.gear-detail-head p,.gear-detail-head>div>span,.affix-description,.legacy-note,.gear-stats{font-size:12px}.gear-detail-head>.btn{font-size:11px}.equipment-action>p,.equipment-action>p.action-note,.equipment-reason,.equipment-action>p.equipment-reason{font-size:12px}.equipment-costs,.comparison-table{font-size:12px}.comparison-table caption,.equipment-costs>strong{font-size:11px}.comparison-table th,.comparison-table td{padding-block:9px}.reforge-result article strong{font-size:13px}.reforge-result article span,.reforge-result>p,.smelt-confirm p{font-size:12px}.reforge-result .btn{min-height:44px;font-size:12px}.list-count{margin-bottom:1px}.material-stock span{font-size:10px}.smelt-confirm>.btn{min-height:44px}}
</style>
