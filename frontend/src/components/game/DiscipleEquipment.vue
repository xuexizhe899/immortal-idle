<script setup lang="ts">
import { computed } from 'vue'
import ItemIcon from './ItemIcon.vue'
import { effectText } from '../../presentation/gameText'
import { useGameStore } from '../../stores/game'
import type { DiscipleState } from '../../api/client'

const props = defineProps<{ disciple: DiscipleState; readOnly?: boolean }>()
const store = useGameStore()
const weapon = computed(() => store.weapons.find(item => item.template_id === props.disciple.template_id))
const equipped = computed(() => store.weapons.find(item => props.disciple.equipment.includes(item.id)))
const unknown = computed(() => props.disciple.equipment.filter(id => !store.weapons.some(item => item.id === id)))
const onRun = computed(() => props.disciple.busy || (store.state?.active_run?.party.includes(props.disciple.id) ?? false))
const stats = computed(() => weapon.value
  ? Object.entries(weapon.value.stats).map(([stat, value]) => effectText({ stat, mode: 'add_pct', value })).join(' · ')
  : '')
const reason = computed(() => {
  if (!weapon.value || equipped.value) return ''
  if (props.readOnly || onRun.value) return '出征期间不可换装'
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
</script>
<template>
  <section v-if="weapon || unknown.length" class="equipment-section">
    <div class="section-heading"><h4>专属武器</h4><span v-if="equipped" class="badge">已装备</span></div>
    <div v-if="equipped" class="weapon-row">
      <ItemIcon :id="equipped.id" :size="40" />
      <div><strong>{{ equipped.name }}</strong><p>{{ stats }}</p></div>
      <button class="btn btn-small" :disabled="store.busy || readOnly || onRun" @click="unequip">卸下</button>
    </div>
    <div v-else-if="weapon" class="weapon-row">
      <ItemIcon :id="weapon.id" :size="40" />
      <div><strong>{{ weapon.name }}</strong><p>{{ stats }}</p><p class="muted">{{ reason || '在行囊中，可以装备。' }}</p></div>
      <button v-if="weapon.in_inventory" class="btn btn-small" :disabled="store.busy || readOnly || onRun" @click="equip">装备</button>
    </div>
    <p v-if="unknown.length" class="muted equipment-note">旧装备未识别：{{ unknown.join('、') }}（保留但不生效）</p>
    <p v-if="readOnly" class="muted equipment-note">出征期间装备锁定，结算后可调整。</p>
  </section>
</template>
<style scoped>
.equipment-section{padding-top:16px;border-top:1px solid #d3c8aa;margin-top:16px}.equipment-section h4{margin:0;font-size:14px}.weapon-row{display:flex;align-items:center;gap:12px;margin-top:10px;padding:10px;background:#e7e5d4;border:1px solid #d0c5a5}.weapon-row>div{flex:1;min-width:0}.weapon-row strong{display:block;font-size:13px}.weapon-row p{margin:4px 0 0;font-size:10px;color:var(--jade)}.weapon-row .muted{color:var(--muted)}.equipment-note{font-size:10px;margin:8px 0 0}
@media(max-width:640px){.weapon-row{align-items:flex-start;flex-wrap:wrap}.weapon-row .btn{margin-left:auto}}
</style>
