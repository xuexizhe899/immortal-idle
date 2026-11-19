<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DiscipleState, GearView } from '../../api/client'
import { equipmentAffixText, equipmentComparison, equipmentPercent, equipmentSlotNames, equipmentSlots, equipmentStats } from '../../presentation/equipment'
import GearIcon from './GearIcon.vue'
import ItemIcon from './ItemIcon.vue'
import { effectText } from '../../presentation/gameText'
import { useGameStore } from '../../stores/game'

const props = defineProps<{ disciple: DiscipleState; readOnly?: boolean }>()
const store = useGameStore()
const selectedSlot = ref<GearView['slot']>('weapon')
const selectedId = ref('')
const pickerOpen = ref(false)
const loading = ref(false)
let loadRequest = 0
const weapon = computed(() => store.weapons.find(item => item.template_id === props.disciple.template_id))
const equipped = computed(() => store.weapons.find(item => props.disciple.equipment.includes(item.id)))
const unknown = computed(() => props.disciple.equipment.filter(id => !store.weapons.some(item => item.id === id)))
const onRun = computed(() => props.disciple.busy || (store.state?.active_run?.party.includes(props.disciple.id) ?? false))
const slots = computed(() => store.gearRules?.slots ?? equipmentSlotNames)
const current = computed(() => slotGear(selectedSlot.value))
const candidates = computed(() => store.gearList.filter(item => item.slot === selectedSlot.value))
const candidate = computed(() => candidates.value.find(item => item.id === selectedId.value))
const currentStats = computed(() => current.value?.stats ?? (selectedSlot.value === 'weapon' ? equipped.value?.stats ?? {} : {}))
const comparison = computed(() => candidate.value ? equipmentComparison(currentStats.value, candidate.value.stats) : [])
const equipReason = computed(() => {
  if (props.readOnly || onRun.value) return '出征期间不可换装'
  if (!candidate.value) return '请选择一件装备'
  if (candidate.value.equipped_by === props.disciple.id) return '已穿戴这件装备'
  if (candidate.value.slot === 'weapon' && equipped.value) return '请先卸下当前专属武器'
  return candidate.value.equip_reason
})
const stats = computed(() => weapon.value
  ? Object.entries(weapon.value.stats).map(([stat, value]) => effectText({ stat, mode: 'add_pct', value })).join(' · ')
  : '')
const reason = computed(() => {
  if (!weapon.value || equipped.value) return ''
  if (props.readOnly || onRun.value) return '出征期间不可换装'
  if (slotGear('weapon')) return '请先卸下当前普通武器'
  if (weapon.value.equipped_by) return '该专武已由其他弟子装备'
  if (!weapon.value.owned) return weapon.value.reason || '尚未获得专属武器'
  return ''
})
async function equip() {
  if (weapon.value) await store.equipWeapon(weapon.value.id, props.disciple.id)
}
async function unequip() {
  await store.unequipWeapon(props.disciple.id)
}
function slotGear(slot: string) { return store.gearList.find(item => item.id === props.disciple.gear_slots[slot]) }
function slotName(slot: string) {
  return slotGear(slot)?.name ?? (slot === 'weapon' && equipped.value ? equipped.value.name : props.disciple.gear_slots[slot] ? '装备资料待查阅' : '尚未穿戴')
}
function ownerName(id: string | null) {
  const owner = store.disciples.find(item => item.id === id)
  return owner ? store.catalog?.disciples[owner.template_id]?.name ?? owner.template_id : '行囊中'
}
function openSlot(slot: GearView['slot']) { selectedSlot.value = slot; pickerOpen.value = true }
async function refresh() {
  const request = ++loadRequest
  loading.value = true
  try { await Promise.all([store.loadEquipment(true), store.loadWeapons()]) }
  finally { if (request === loadRequest) loading.value = false }
}
watch([() => store.slotId, () => store.revision], () => { void refresh() }, { immediate: true })
watch(() => props.disciple.id, () => { pickerOpen.value = false; selectedSlot.value = 'weapon' })
watch(candidates, items => {
  if (!items.some(item => item.id === selectedId.value)) selectedId.value = items.find(item => item.equipped_by !== props.disciple.id)?.id ?? items[0]?.id ?? ''
}, { immediate: true })
</script>
<template>
  <section class="equipment-section">
    <div class="section-heading"><h4>个人装备</h4><span class="muted">四个部位，独立培养</span></div>
    <div class="equipment-slots"><button v-for="slot in equipmentSlots" :key="slot" :class="{active:pickerOpen&&selectedSlot===slot,filled:!!slotGear(slot)||(slot==='weapon'&&!!equipped)}" :aria-pressed="pickerOpen&&selectedSlot===slot" @click="openSlot(slot)"><GearIcon :slot="slot" :size="29" /><span><small>{{ slots[slot]??equipmentSlotNames[slot] }}</small><strong>{{ slotName(slot) }}</strong><em v-if="slotGear(slot)">强化 +{{ slotGear(slot)?.level }}</em><em v-else-if="slot==='weapon'&&equipped">专属 · {{ equipped.level }} 级</em></span></button></div>
    <p v-if="readOnly||onRun" class="equipment-note">出征期间装备锁定，结算后可调整。</p>
    <p v-if="loading" class="equipment-note" role="status">正在查阅装备……</p>
    <p v-if="!loading&&!store.gearRules" class="equipment-note">装备资料尚未取到。<button class="text-button" :disabled="store.busy" @click="refresh">重新查阅</button></p>
    <section v-if="pickerOpen" class="slot-picker" :aria-label="`${slots[selectedSlot]}装备选择`">
      <header><h5>{{ slots[selectedSlot]??equipmentSlotNames[selectedSlot] }}</h5><button class="btn btn-small btn-quiet" @click="pickerOpen=false">收起</button></header>
      <div v-if="current" class="current-equipment"><strong>当前：{{ current.name }} +{{ current.level }}</strong><p>{{ equipmentStats(current.stats).map(stat=>stat.name+' '+stat.text).join(' · ') }}</p><button class="btn btn-small" :disabled="store.busy||readOnly||onRun||!!current.unequip_reason" @click="store.equipmentAction('unequip',current.id)">卸下当前装备</button><p v-if="current.unequip_reason" class="equipment-reason">{{ current.unequip_reason }}</p></div>
      <div v-if="candidates.length" class="candidate-list" aria-label="同部位普通装备"><button v-for="item in candidates" :key="item.id" :class="{active:selectedId===item.id}" :aria-pressed="selectedId===item.id" @click="selectedId=item.id"><strong>{{ item.name }} <small>+{{ item.level }}</small></strong><span>{{ item.tier }} 阶 · {{ item.equipped_by===disciple.id?'当前穿戴':item.equipped_by?ownerName(item.equipped_by)+'穿戴中':'行囊中' }}{{ item.locked?' · 已锁定':'' }}</span></button></div>
      <p v-else class="equipment-note">暂无这一部位的普通装备。探索秘境、挑战首领后可结算带回。</p>
      <article v-if="candidate" class="candidate-detail"><strong>{{ candidate.name }} +{{ candidate.level }}</strong><p class="candidate-affix">{{ equipmentAffixText(candidate.affix,candidate.affix_value,candidate.affix_grade) }}</p><table class="equip-comparison"><caption>同部位装备增益对比</caption><thead><tr><th scope="col">属性</th><th scope="col">当前</th><th scope="col">候选</th></tr></thead><tbody><tr v-for="row in comparison" :key="row.stat"><th scope="row">{{ row.name }}</th><td>{{ equipmentPercent(row.current) }}</td><td :class="{better:row.delta>0,worse:row.delta<0}">{{ equipmentPercent(row.candidate) }}<small v-if="row.delta">{{ row.delta>0?'↑':'↓' }}</small></td></tr></tbody></table><p v-if="candidate.equipped_by&&candidate.equipped_by!==disciple.id" class="transfer-note">穿戴后，这件装备会从{{ ownerName(candidate.equipped_by) }}转交给当前弟子。</p><p v-if="equipReason" class="equipment-reason">{{ equipReason }}</p><button class="btn btn-primary equip-button" :disabled="store.busy||!!equipReason" @click="store.equipmentAction('equip',candidate.id,{disciple_id:disciple.id})">{{ candidate.equipped_by===disciple.id?'当前已穿戴':candidate.equipped_by?'转交并穿戴':'穿戴这件装备' }}</button></article>
      <section v-if="selectedSlot==='weapon'&&weapon" class="special-weapon"><h5>专属武器</h5><div class="weapon-row"><ItemIcon :id="weapon.id" :size="36" /><div><strong>{{ weapon.name }}{{ weapon.owned?' · '+weapon.level+' 级':'' }}</strong><p>{{ stats }}</p></div></div><p v-if="reason" class="equipment-reason">{{ reason }}</p><p v-if="equipped" class="equipment-note">已穿戴，占用武器部位。</p><button v-if="equipped" class="btn btn-small" :disabled="store.busy||readOnly||onRun" @click="unequip">卸下专属武器</button><button v-else-if="weapon.in_inventory" class="btn btn-small" :disabled="store.busy||!!reason" @click="equip">穿戴专属武器</button><p v-else-if="!weapon.owned" class="equipment-note">可前往炼器阁查看专武锻造条件。</p></section>
    </section>
    <p v-if="unknown.length" class="equipment-note">有 {{ unknown.length }} 件旧专武记录尚未识别，暂不提供装备增益。</p>
  </section>
</template>
<style scoped>
.equipment-section{padding-top:16px;border-top:1px solid #d3c8aa;margin-top:16px}.equipment-section .section-heading{gap:7px;margin-bottom:11px}.equipment-section h4{margin:0;font-size:15px}.equipment-section .section-heading>.muted{font-size:10px}.equipment-slots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.equipment-slots>button{display:flex;gap:7px;align-items:center;min-height:82px;min-width:0;padding:8px 6px;text-align:left;border:1px dashed #babc9f;background:#e7e6d4}.equipment-slots>button.filled{border-style:solid;background:#e1e7d2}.equipment-slots>button.active{border-color:var(--jade);box-shadow:inset 0 0 0 1px var(--jade)}.equipment-slots>button>span{min-width:0}.equipment-slots small,.equipment-slots strong,.equipment-slots em{display:block}.equipment-slots small{font-size:9px;color:#7d855f}.equipment-slots strong{font:12px 'SimSun',serif;line-height:1.5;overflow-wrap:anywhere;color:var(--jade)}.equipment-slots em{font-size:9px;font-style:normal;color:#8a794c;margin-top:3px}.equipment-note{font-size:10px;color:var(--muted);line-height:1.8;margin:9px 0 0}.text-button{font-size:inherit;border:0;background:transparent;padding:3px 5px;color:var(--jade);text-decoration:underline;min-height:32px}.slot-picker{margin-top:12px;padding:10px;background:#f4eedc;border:1px solid #bebc9d}.slot-picker>header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #d3c8aa;padding-bottom:6px;margin-bottom:10px}.slot-picker h5{font:16px 'SimSun',serif;color:var(--jade);margin:0}.slot-picker>header .btn{font-size:10px}.current-equipment{padding-bottom:12px;border-bottom:1px solid #d3c8aa;margin-bottom:10px}.current-equipment>strong{font-size:11px;font-weight:500;color:var(--jade)}.current-equipment>p,.weapon-row p{font-size:10px;color:var(--muted);line-height:1.8;margin:5px 0}.current-equipment>.btn{font-size:10px}.candidate-list{display:flex;flex-direction:column;gap:5px;max-height:220px;overflow-y:auto;padding:1px;overscroll-behavior:contain}.candidate-list>button{padding:8px;text-align:left;min-height:50px;border:1px solid #c9c4a7;background:#eae7d5}.candidate-list>button.active{border-color:var(--jade);background:#dce5ce}.candidate-list strong{display:block;font:13px 'SimSun',serif;overflow-wrap:anywhere}.candidate-list strong small{font-size:11px;color:var(--gold)}.candidate-list span{display:block;font-size:9px;color:var(--muted);margin-top:4px}.candidate-detail{padding-top:13px;margin-top:12px;border-top:1px solid #d3c8aa}.candidate-detail>strong{font:16px 'SimSun',serif;color:var(--jade)}.candidate-affix{font-size:10px;color:var(--gold);line-height:1.8;margin:6px 0}.equip-comparison{width:100%;border-collapse:collapse;font-size:10px;font-variant-numeric:tabular-nums}.equip-comparison caption{text-align:left;color:var(--muted);font-size:9px;padding:5px 0}.equip-comparison th,.equip-comparison td{font-weight:400;text-align:right;padding:6px 2px;border-bottom:1px solid #d9cfb3}.equip-comparison tr>:first-child{text-align:left}.equip-comparison thead{color:var(--muted);font-size:9px}.equip-comparison .better{color:var(--jade)}.equip-comparison .worse{color:var(--danger)}.equip-comparison td small{margin-left:2px}.transfer-note{font-size:10px;line-height:1.8;color:#8e713d;margin:9px 0}.equipment-reason{font-size:10px;line-height:1.8;color:var(--danger);margin:9px 0}.equip-button{width:100%;white-space:normal;font-size:11px;padding-inline:8px;margin-top:9px}.special-weapon{border-top:1px solid #c7b998;margin-top:17px;padding-top:12px}.special-weapon h5{font-size:14px}.weapon-row{display:flex;align-items:center;gap:8px;margin:10px 0}.weapon-row>div{min-width:0}.weapon-row strong{font-size:12px;overflow-wrap:anywhere}.special-weapon>.btn{width:100%;font-size:11px;margin-top:9px}
@media(max-width:640px){.equipment-slots>button{padding:10px;gap:10px;min-height:88px}.equipment-slots strong{font-size:14px}.equipment-slots small,.equipment-slots em{font-size:11px}.equipment-section .section-heading>.muted{font-size:11px}.slot-picker{padding:12px}.equipment-note,.equipment-reason,.transfer-note,.candidate-affix{font-size:12px}.current-equipment>strong{font-size:13px}.current-equipment>p,.weapon-row p{font-size:12px}.candidate-list{max-height:250px}.candidate-list>button{padding:11px}.candidate-list strong{font-size:15px}.candidate-list span{font-size:11px}.equip-comparison{font-size:12px}.equip-comparison caption,.equip-comparison thead{font-size:11px}.equip-comparison th,.equip-comparison td{padding-block:9px}.equip-button,.special-weapon>.btn,.current-equipment>.btn{font-size:12px;min-height:44px}.weapon-row strong{font-size:14px}.text-button{min-height:44px}}
</style>
