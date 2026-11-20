<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { GearView } from '../api/client'
import GearIcon from '../components/game/GearIcon.vue'
import PanelModal from '../components/ui/PanelModal.vue'
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
const detailOpen = ref(false)
const detailModal = ref<InstanceType<typeof PanelModal> | null>(null)
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
watch(() => store.slotId, () => { closeEquipment(); selectedId.value = ''; void refresh() }, { immediate: true })
watch(() => store.revision, () => { void refresh(true) })
watch(filtered, items => {
  if (!items.some(item => item.id === selectedId.value)) { closeEquipment(); selectedId.value = '' }
}, { immediate: true })
watch(selectedId, () => { confirmSmelt.value = false })
watch(detailTab, () => { confirmSmelt.value = false; nextTick(() => detailModal.value?.resetScroll()) })
watch(() => selected.value?.pending_affix, pending => { if (pending) detailTab.value = 'reforge' }, { immediate: true })
function openEquipment(id: string) {
  if (!filtered.value.some(item => item.id === id)) return
  selectedId.value = id
  detailTab.value = selected.value?.pending_affix ? 'reforge' : 'upgrade'
  confirmSmelt.value = false
  detailOpen.value = true
}
function closeEquipment() { detailOpen.value = false; confirmSmelt.value = false }
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
    <div class="equipment-intro"><div><h3>个人装备</h3><p>武器、盔甲、靴子与戒指，增益只属于穿戴它的弟子。</p><span class="equipment-total">共 {{ store.gearList.length }} 件 · {{ store.gearList.filter(item=>!!item.equipped_by).length }} 件已穿戴</span></div><div class="material-stock"><span>{{ materialName }}</span><strong>{{ number(held(material)) }}</strong><small>用于装备提升</small></div></div>
    <p v-if="readOnly" class="notice-box">出征尚未结算，可查阅装备；结算后可强化、洗练和熔炼。</p>
    <div class="equipment-toolbar"><div class="slot-filters" aria-label="筛选装备部位"><button :class="{active:slotFilter==='all'}" :aria-pressed="slotFilter==='all'" @click="slotFilter='all'">全部</button><button v-for="slot in equipmentSlots" :key="slot" :class="{active:slotFilter===slot}" :aria-pressed="slotFilter===slot" @click="slotFilter=slot">{{ slots[slot]??equipmentSlotNames[slot] }}</button></div><div class="equipment-search"><select v-model="ownerFilter" aria-label="筛选装备归属"><option value="all">全部归属</option><option value="bag">行囊中</option><option value="equipped">已穿戴</option><option value="pending">待选洗练</option></select><input v-model="search" aria-label="查找装备" placeholder="查找装备" /><button class="btn btn-small" :disabled="store.busy||loading" @click="refresh()">{{ loading?'查阅中…':'刷新' }}</button></div></div>
    <p v-if="loadFailed" class="error-box" role="alert">装备资料暂未取到，请刷新后重试。</p>
    <p v-if="loading&&!store.gearList.length" class="notice-box" role="status">正在查阅装备与材料……</p>
    <div v-else-if="!store.gearList.length&&!loadFailed" class="empty-state"><GearIcon slot="weapon" :size="48" /><strong>行囊中还没有普通装备</strong><p>在世界地图探索秘境、挑战首领，结算后即可带回装备。</p><div class="equipment-empty-actions"><button class="btn btn-primary btn-small" @click="emit('open','expedition')">前往山河</button><button class="btn btn-small" @click="emit('open','codex')">查看弟子装备位</button></div></div>
    <div v-else class="equipment-layout">
      <div class="gear-list" aria-label="选择要提升的装备"><p class="list-count">{{ filtered.length }} / {{ store.gearList.length }} 件装备 · 点击查看与提升</p><button v-for="item in filtered" :key="item.id" :class="{active:selectedId===item.id,pending:!!item.pending_affix}" :aria-pressed="selectedId===item.id" aria-haspopup="dialog" @click="openEquipment(item.id)"><GearIcon :slot="item.slot" :size="34" /><span><strong>{{ item.name }} <small>+{{ item.level }}</small></strong><small>{{ item.tier }} 阶 · {{ slots[item.slot]??item.slot }} · {{ item.equipped_by?ownerName(item.equipped_by):'行囊中' }}</small><em v-if="item.pending_affix">待选择洗练结果</em><em v-else-if="item.locked" class="locked-label">已锁定</em></span></button><p v-if="!filtered.length" class="filter-empty">没有符合条件的装备，可切换部位或归属。</p></div>
    </div>
    <PanelModal v-if="detailOpen&&selected" ref="detailModal" :title="selected.name" subtitle="个人装备提升" @close="closeEquipment">
      <article class="gear-detail">
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
    </PanelModal>
  </section>
</template>

<style scoped>
.equipment-intro{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:16px 0 18px;border-bottom:1px solid var(--border)}.equipment-intro h3{font-size:23px;margin:0 0 6px}.equipment-intro p{font-size:12px;color:var(--muted);margin:0;max-width:42em}.material-stock{flex:none;text-align:right;color:var(--jade)}.material-stock span{display:block;font-size:11px;color:var(--muted)}.material-stock strong{font:25px 'SimSun',serif;font-variant-numeric:tabular-nums}.equipment-workshop>.notice-box{margin-top:14px}.equipment-toolbar{margin:16px 0;display:flex;flex-direction:column;gap:10px}.slot-filters{display:flex;flex-wrap:wrap;gap:5px}.slot-filters button,.detail-tabs button{border:1px solid transparent;background:transparent;color:var(--muted);padding:7px 13px;min-height:36px;font-size:12px}.slot-filters button.active,.detail-tabs button.active{border-color:#9caf8b;background:#e0e7d1;color:var(--jade)}.equipment-search{display:flex;gap:7px}.equipment-search select,.equipment-search input{font-size:11px;min-height:36px;padding:6px 9px}.equipment-search select{width:115px}.equipment-search input{width:0;flex:1}.equipment-layout{min-width:0}.gear-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;max-height:440px;overflow-y:auto;overscroll-behavior:contain;padding:1px}.list-count{grid-column:1 / -1;font-size:10px;color:var(--muted);margin:0 0 8px}.gear-list>button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:10px 8px;margin:0;background:#eee9d7;border:1px solid #c9c4a7}.gear-list>button.active{border-color:var(--jade);background:#dfe7d1;box-shadow:inset 3px 0 var(--jade)}.gear-list>button.pending{border-right:3px solid var(--gold)}.gear-list>button>span{min-width:0}.gear-list strong{display:block;font:14px 'SimSun',serif;overflow-wrap:anywhere}.gear-list strong>small{font-size:12px;color:var(--gold)}.gear-list span>small{display:block;font-size:9px;color:var(--muted);line-height:1.7;margin-top:4px}.gear-list em{display:block;margin-top:4px;font-size:9px;font-style:normal;color:#9b702e}.gear-list em.locked-label{color:#6e7f62}.filter-empty{grid-column:1 / -1;padding:15px 8px;font-size:12px;line-height:1.8;color:var(--muted)}.gear-detail{min-width:0;padding:17px;background:#f5efdd;border:1px solid #c5b895}.gear-detail-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.gear-detail-head>div{flex:1;min-width:100px}.gear-detail-head>div>span{font-size:10px;color:var(--gold)}.gear-detail-head h4{font-size:21px;margin:4px 0;overflow-wrap:anywhere}.gear-detail-head h4 small{font-size:15px;color:var(--gold)}.gear-detail-head p{font-size:10px;color:var(--muted);margin:0}.gear-detail-head>.btn{margin-left:auto;font-size:10px}.gear-stats{display:flex;gap:5px 14px;flex-wrap:wrap;margin:15px 0 8px;padding:12px 0;border-block:1px solid #d8cfb5;font-size:11px;color:var(--muted)}.gear-stats strong{font-weight:500;color:var(--jade);font-variant-numeric:tabular-nums}.affix-description,.legacy-note{font-size:10px;color:var(--muted);line-height:1.8;margin:6px 0}.legacy-note{color:#8b794d}.detail-tabs{display:flex;gap:4px;margin:18px 0 14px;padding-bottom:7px;border-bottom:1px solid var(--border)}.detail-tabs button{position:relative;flex:1;padding-inline:8px}.pending-dot{display:inline-block;width:5px;height:5px;vertical-align:middle;background:var(--gold);margin-left:5px;transform:rotate(45deg)}.equipment-action h5{font:18px 'SimSun',serif;margin:0 0 8px;color:var(--jade)}.equipment-action>p{font-size:11px;color:var(--muted);line-height:1.8;margin:6px 0 12px}.comparison-table{width:100%;border-collapse:collapse;margin:14px 0;font-size:11px;font-variant-numeric:tabular-nums}.comparison-table caption{text-align:left;font-size:10px;color:var(--muted);padding-bottom:6px}.comparison-table th,.comparison-table td{text-align:right;border-bottom:1px solid #d9d0b7;padding:7px 5px;font-weight:400}.comparison-table tr>:first-child{text-align:left;color:var(--muted)}.comparison-table thead th{font-size:10px;color:var(--muted)}.comparison-table td.improved{color:var(--jade);font-weight:600}.equipment-costs{display:flex;flex-direction:column;gap:7px;padding:11px 0;border-block:1px solid #d8cfb5;font-size:11px;margin:12px 0}.equipment-costs>strong{font-weight:500;color:var(--muted);font-size:10px}.equipment-costs>span{display:flex;justify-content:space-between;gap:8px}.equipment-costs b{font-weight:500;color:var(--jade);font-variant-numeric:tabular-nums}.equipment-costs .missing,.equipment-costs .missing b{color:var(--danger)}.equipment-reason,.equipment-action>p.equipment-reason{color:var(--danger);font-size:11px;line-height:1.8;margin:10px 0}.action-button{width:100%;margin-top:8px;white-space:normal;min-height:42px}.reforge-result article{padding:12px;border:1px solid #c7c7a9;background:#ecead7;margin-top:9px}.reforge-result article span{display:block;font-size:10px;color:var(--muted);margin-bottom:5px}.reforge-result article strong{font-size:12px;font-weight:500;color:var(--jade)}.reforge-result .new-affix{border-color:#bfaa73;background:#f4e9ce}.reforge-result>p{font-size:11px;line-height:1.8;color:var(--muted);margin:12px 0}.reforge-result>div{display:flex;gap:7px;flex-wrap:wrap}.reforge-result .btn{flex:1;font-size:11px;padding-inline:9px}.smelt-confirm{padding:12px;background:#f3e5d5;border:1px solid #c79578;margin-top:13px}.smelt-confirm>strong{font-size:12px;color:var(--danger);overflow-wrap:anywhere}.smelt-confirm p{font-size:11px;color:var(--muted);line-height:1.8;margin:8px 0}.smelt-confirm .btn{font-size:11px;margin-top:5px}.equipment-action>p.action-note{font-size:10px}.equipment-workshop .empty-state p{font-size:12px;line-height:1.9;margin:9px 0 15px}
@media(max-width:640px){.equipment-intro{align-items:flex-start;padding-top:6px}.equipment-intro h3{font-size:21px}.equipment-intro p{font-size:12px;line-height:1.8}.material-stock strong{font-size:22px}.gear-list{max-height:245px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gear-list .list-count,.gear-list .filter-empty{grid-column:1 / -1}.gear-list>button{margin:0;padding:9px 6px;align-items:flex-start;gap:5px}.gear-list>button>.gear-icon{width:28px;height:30px}.gear-list strong{font-size:13px;line-height:1.5}.gear-list span>small,.gear-list em{font-size:10px}.gear-detail{padding:14px}.equipment-search{flex-wrap:wrap}.equipment-search select{width:110px}.equipment-search input{min-width:80px}.equipment-search select,.equipment-search input,.equipment-search .btn,.slot-filters button,.detail-tabs button{min-height:44px}.slot-filters button{padding-inline:12px}.gear-detail-head h4{font-size:22px}.gear-detail-head p,.gear-detail-head>div>span,.affix-description,.legacy-note,.gear-stats{font-size:12px}.gear-detail-head>.btn{font-size:11px}.equipment-action>p,.equipment-action>p.action-note,.equipment-reason,.equipment-action>p.equipment-reason{font-size:12px}.equipment-costs,.comparison-table{font-size:12px}.comparison-table caption,.equipment-costs>strong{font-size:11px}.comparison-table th,.comparison-table td{padding-block:9px}.reforge-result article strong{font-size:13px}.reforge-result article span,.reforge-result>p,.smelt-confirm p{font-size:12px}.reforge-result .btn{min-height:44px;font-size:12px}.list-count{margin-bottom:1px}.material-stock span{font-size:10px}.smelt-confirm>.btn{min-height:44px}}
.equipment-intro{padding:5px 0 15px;align-items:flex-start;border-bottom-color:#c5cbae}.equipment-intro h3{color:#213f36;font-size:22px}.equipment-intro p{font-size:11px;line-height:1.8;max-width:36em}.equipment-total{display:block;font-size:10px;color:#8c6844;margin-top:8px;font-variant-numeric:tabular-nums}.material-stock{border-left:1px solid #c6cdb1;padding-left:16px;min-width:89px}.material-stock>span{color:#6b785e;font-size:10px}.material-stock>strong{font-size:28px;color:#326c55;line-height:1.6}.material-stock>small{font-size:9px;color:#8a8c70}.equipment-toolbar{padding:0 0 13px;border-bottom:1px solid #d4d8bf;margin-bottom:10px}.slot-filters{gap:4px}.slot-filters>button{border-bottom:2px solid #d5dbc2;min-height:44px;background:#f0f0df}.slot-filters>button.active{background:#e3ebd5;border-color:#b4c2a1;border-bottom-color:#326c55}.equipment-search select,.equipment-search input{background:#f6f1df;border-color:#bfc7aa}.list-count{margin:0;padding:2px 0 7px;font-size:10px}.gear-list{gap:8px;scrollbar-gutter:stable}.gear-list>button{position:relative;min-height:86px;align-items:flex-start;padding:12px 10px;background:#f6f1df;border-color:#c7cbb0;border-bottom:2px solid #bcc8a7}.gear-list>button.active{background:#e7eeda;border-color:#7d9a74;box-shadow:inset 3px 0 #326c55}.gear-list>button.pending{border-right-color:#b38a46}.gear-list>button>.gear-icon{flex:none;margin-top:2px}.gear-list strong{font-size:15px;line-height:1.5;color:#213f36}.gear-list strong>small{color:#8c6844}.gear-list span>small{font-size:10px;line-height:1.7}.gear-list em{font-size:10px}.gear-list>button.pending>span>em{display:inline-block;color:#7b5e22;background:#eee5c7;padding:1px 5px;border:1px solid #c9b77d}.gear-detail{background:#f6f1df;border-color:#b8c5a4;border-top:3px solid #326c55}.gear-detail-head{padding-bottom:13px;border-bottom:1px solid #d7d9be}.gear-detail-head h4{color:#213f36}.gear-stats{border-top:0;margin-top:0;padding:13px 0;gap:9px 15px}.gear-stats>span{flex:1 0 40%;display:flex;justify-content:space-between;gap:12px}.detail-tabs button.active{border-color:#a9ba97;background:#e3ebd5;box-shadow:inset 0 -2px #326c55}.comparison-table thead{background:#e7ecd9}.comparison-table td.improved{background:#eef1df}.equipment-costs{padding:12px;background:#efefdd;border-color:#cdd4b8}.reforge-result>article{border-left:3px solid #95a482;background:#edf0de}.reforge-result>.new-affix{border-left-color:#b38a46}.equipment-workshop .empty-state{padding:23px 14px;border:1px dashed #b9c6a6;background:#f1f1df}.equipment-workshop .empty-state>.gear-icon{margin-bottom:9px}.equipment-workshop .empty-state>strong{font:20px 'SimSun',serif;color:#326c55}.equipment-empty-actions{display:flex;justify-content:center;gap:8px;flex-wrap:wrap}.equipment-workshop button:focus-visible{outline:2px solid #326c55;outline-offset:2px}
@media(max-width:640px){.equipment-intro{gap:12px}.equipment-intro h3{font-size:21px}.equipment-intro p{font-size:11px}.equipment-total{font-size:11px;line-height:1.8}.material-stock{min-width:76px;padding-left:10px}.material-stock>strong{font-size:25px}.material-stock>small{font-size:9px}.equipment-toolbar{gap:11px}.gear-list{gap:6px;max-height:min(45dvh,340px)}.gear-list>button{min-height:104px;padding:10px 7px;gap:5px}.gear-list strong{font-size:14px}.gear-list>button>.gear-icon{width:28px;height:30px}.gear-list span>small{font-size:10px}.gear-stats{font-size:12px}.gear-stats>span{flex-basis:100%}.gear-detail-head h4{font-size:21px}.equipment-empty-actions>.btn{min-height:44px;font-size:12px}.equipment-workshop .empty-state{padding:18px 12px}}
</style>

<style scoped>
/* 个人装备使用深色工作台，选中态只用边缘和颜色区分，避免重复卡片层级。 */
.equipment-intro { border-bottom-color: var(--line-faint); }
.equipment-intro h3, .gear-list strong, .gear-detail-head h4 { color: var(--ink); }
.equipment-total, .material-stock > small { color: var(--muted); }
.material-stock { border-left-color: var(--border); }
.material-stock > strong { color: var(--jade); }
.equipment-toolbar { border-bottom-color: var(--line-faint); }
.slot-filters > button { background: transparent; border-bottom-color: var(--line-faint); }
.slot-filters > button.active { background: var(--jade-light); border-color: var(--border); border-bottom-color: var(--jade); color: var(--jade); }
.equipment-search select, .equipment-search input { background: var(--surface-raised); border-color: var(--border); color: var(--text); }
.gear-list > button { background: var(--surface-raised); border-color: var(--border); border-bottom-color: var(--border); }
.gear-list > button:hover:not(:disabled) { background: #29443f; }
.gear-list > button.active { background: var(--jade-light); border-color: var(--jade); box-shadow: inset 3px 0 var(--jade); }
.gear-list > button.pending { border-right-color: var(--gold); }
.gear-list strong > small { color: var(--gold); }
.gear-list > button.pending > span > em { color: var(--gold); background: #3d3220; border-color: #8b6e3e; }
.gear-detail { background: var(--surface-raised); border-color: var(--border); border-top-color: var(--jade); }
.gear-detail-head { border-bottom-color: var(--line-faint); }
.gear-detail-head h4 small { color: var(--gold); }
.gear-stats { border-bottom-color: var(--line-faint); }
.detail-tabs button.active { background: var(--jade-light); border-color: var(--border); box-shadow: inset 0 -2px var(--jade); color: var(--jade); }
.comparison-table th, .comparison-table td { border-bottom-color: var(--line-faint); }
.comparison-table thead { background: var(--surface-inset); }
.comparison-table td.improved { background: rgba(125,214,173,.08); }
.equipment-costs { background: var(--surface-inset); border-color: var(--line-faint); }
.reforge-result > article { border-color: var(--border); border-left-color: var(--jade-deep); background: var(--surface-inset); }
.reforge-result > .new-affix { border-left-color: var(--gold); background: #3d3220; }
.smelt-confirm { background: #3b2824; border-color: #865247; }
.equipment-workshop .empty-state { border-color: var(--border); background: var(--surface-inset); }
.equipment-workshop .empty-state > strong { color: var(--jade); }
.equipment-workshop button:focus-visible { outline-color: var(--gold); }
@media (max-width: 640px) {
  .material-stock { padding-left: 10px; }
  .gear-list { max-height: 300px; }
  .gear-list > button { min-height: 82px; }
}
</style>
