<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import ItemIcon from '../components/game/ItemIcon.vue'
import type { RecipeView, WeaponView } from '../api/client'
import { effectText, injuryText, resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

const props = defineProps<{ kind?: string; readOnly?: boolean }>()
const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const grade = ref(1)
const quantity = ref(1)
const selectedId = ref('')
const previews = ref<RecipeView[]>([])
const loading = ref(false)
const useItem = ref('')
const useTarget = ref('')
let previewRequest = 0
const recipes = computed(() => previews.value.filter(recipe => !props.kind || recipe.kind === props.kind))
const recipe = computed(() => recipes.value.find(item => item.id === selectedId.value))
const maxGrade = computed(() => store.state?.facility_levels.alchemy ?? 1)
const isPill = computed(() => props.kind === 'pill')
const reason = computed(() => {
  if (props.readOnly) return '出征期间仅可查阅，结算后可继续炼制'
  if (loading.value) return '正在核对配方'
  if (!recipe.value) return '请选择配方'
  if (recipe.value.reason) return recipe.value.reason
  if (!Number.isInteger(quantity.value) || quantity.value < 1) return '请输入正整数数量'
  if (quantity.value > recipe.value.max_quantity) return '材料不足以炼制所选数量'
  return ''
})
const inventory = computed(() => {
  const counts = new Map(Object.entries(store.state?.inventory ?? {}).filter(([, count]) => count > 0))
  const old = counts.get('healing_pill') ?? 0
  if (old) {
    counts.delete('healing_pill')
    counts.set('liao_shang_dan', (counts.get('liao_shang_dan') ?? 0) + old)
  }
  return [...counts.entries()]
})
const pills = computed(() => inventory.value.filter(([id]) => store.catalog?.recipes[id.split(':')[0]!]?.kind === 'pill'))
const basePillId = computed(() => useItem.value.split(':')[0] ?? '')
const pillDefinition = computed(() => store.catalog?.recipes[basePillId.value])
const target = computed(() => store.disciples.find(d => d.id === useTarget.value))
const useReason = computed(() => {
  if (props.readOnly) return '出征期间不可服用'
  if (!useItem.value) return '行囊中没有可服用的丹药'
  if (!target.value) return '请选择服用弟子'
  if (target.value.busy) return '弟子正在出征'
  if (pillDefinition.value?.special === 'heal' && !target.value.injury_stacks) return '该弟子没有伤势'
  return ''
})
const usedGrades = computed(() => target.value?.pill_grades[basePillId.value]
  ?? Array(target.value?.pill_uses[basePillId.value] ?? 0).fill(1))
watch([grade, () => store.revision, () => store.slotId], async () => {
  const request = ++previewRequest
  loading.value = true
  previews.value = []
  const result = await store.previewRecipes(grade.value)
  if (request !== previewRequest) return
  previews.value = result?.recipes ?? []
  loading.value = false
  if (!recipes.value.some(item => item.id === selectedId.value)) selectedId.value = recipes.value[0]?.id ?? ''
}, { immediate: true })
watch([selectedId, grade], () => { quantity.value = 1 })
watch(maxGrade, limit => {
  if (grade.value > limit) grade.value = 1
})
watch(pills, list => {
  if (!list.some(([id]) => id === useItem.value)) useItem.value = list[0]?.[0] ?? ''
}, { immediate: true })
watch(() => store.revision, () => { void store.loadWeapons() })
onMounted(() => { void store.loadWeapons() })
function held(id: string) { return store.state?.inventory[id] ?? 0 }
function findMaterial(id: string) {
  emit('open', store.planProduction(id))
}
function discipleName(id: string) {
  const disciple = store.disciples.find(d => d.id === id)
  return disciple ? store.catalog?.disciples[disciple.template_id]?.name ?? id : id
}
function weaponCosts(weapon: WeaponView) { return weapon.owned ? weapon.upgrade_inputs : weapon.inputs }
function weaponReason(weapon: WeaponView) {
  if (props.readOnly) return '出征结束后可继续锻造'
  return weapon.owned ? weapon.upgrade_reason : weapon.reason
}
async function craft() {
  if (!recipe.value || reason.value) return
  await store.craft(recipe.value.id, recipe.value.kind === 'pill' ? quantity.value : 1, recipe.value.grade)
}
</script>

<template>
  <div class="craft-workshop">
    <div class="section-heading">
      <div>
        <span class="eyebrow">{{ isPill ? '炉火温养 · 因材炼丹' : '百炼成器 · 以器助道' }}</span>
        <h3>
          {{ isPill ? '炼丹房' : '炼器炉' }}
          <small>{{ store.state?.facility_levels[isPill?'alchemy':'forge'] ?? 1 }} 级</small>
        </h3>
      </div>
      <button class="btn btn-small btn-quiet" @click="emit('open','sect')">查看设施升级</button>
    </div>
    <label v-if="isPill" class="grade-control">
      炼制品级
      <select v-model.number="grade">
        <option v-for="i in maxGrade" :key="i" :value="i">{{ i }} 品</option>
      </select>
      <span class="muted">高阶属性丹可替换低阶效果</span>
    </label>
    <p v-if="loading" class="notice-box" role="status">正在查阅配方与可炼数量……</p>
    <div v-else class="craft-layout">
      <div class="recipe-list" aria-label="选择配方">
        <button
          v-for="item in recipes"
          :key="item.id"
          :class="{active:selectedId===item.id}"
          :aria-pressed="selectedId===item.id"
          @click="selectedId=item.id"
        >
          <ItemIcon :id="item.id" />
          <span>
            <strong>{{ item.name }}</strong>
            <small>
              {{ item.kind==='pill' ? item.grade+'品 · 库存 '+item.stock : item.current_level ? '当前 '+item.current_level+' 级' : '尚未打造' }}
            </small>
          </span>
        </button>
      </div>
      <article v-if="recipe" class="recipe-detail">
        <div class="recipe-head">
          <ItemIcon :id="recipe.id" variant="display" />
          <div>
            <span class="eyebrow">{{ recipe.kind==='pill' ? recipe.grade+'品丹方' : '器具提升' }}</span>
            <h3>{{ recipe.name }}</h3>
            <p>
              {{ recipe.kind==='pill' ? '本次炼制 '+quantity+' 颗' : recipe.current_level>=recipe.max_grade ? '已达到设施允许的最高等级' : recipe.current_level ? recipe.current_level+' → '+recipe.grade+' 级' : '打造 1 级器具' }}
            </p>
          </div>
        </div>
        <div class="recipe-effects">
          <span v-for="(effect,index) in recipe.effects" :key="index">{{ effectText(effect) }}</span>
          <span v-if="store.catalog?.recipes[recipe.id]?.special==='heal'">清除目标全部伤势</span>
          <span v-if="store.catalog?.recipes[recipe.id]?.special==='realm'">达到当前境界等级上限后，境界提升一重</span>
        </div>
        <p v-if="recipe.kind==='artifact'" class="muted">升级替换这件器具的旧增益，其他器具加成保留。</p>
        <div class="ingredient-list">
          <div v-for="(count,id) in recipe.inputs" :key="id" :class="{missing:held(id)<count*quantity}">
            <ItemIcon :id="id" :size="22" />
            <span>{{ resourceName(id,store.catalog) }}</span>
            <strong>{{ held(id) }} / {{ count*quantity }}</strong>
            <button v-if="held(id)<count*quantity" class="btn btn-small btn-quiet" @click="findMaterial(id)">
              {{ store.productionDestination(id).label }}
            </button>
          </div>
        </div>
        <div v-if="recipe.kind==='pill'" class="quantity-control">
          <label>
            数量
            <input
              v-model.number="quantity"
              type="number"
              min="1"
              :max="Math.max(1,recipe.max_quantity)"
              step="1"
              :disabled="readOnly||store.busy"
            />
          </label>
          <button
            class="btn btn-small"
            :disabled="readOnly||store.busy||!recipe.max_quantity"
            @click="quantity=recipe.max_quantity"
          >
            最大可炼
            {{ recipe.max_quantity }}
          </button>
        </div>
        <p v-if="reason" class="craft-reason">{{ reason }}</p>
        <button class="btn btn-primary craft-button" :disabled="store.busy||!!reason" @click="craft">
          {{ recipe.kind==='pill' ? '炼制 '+quantity+' 颗' : recipe.current_level ? '提升器具等级' : '打造器具' }}
        </button>
      </article>
      <p v-else class="notice-box">暂无可用配方，请刷新进度后重试。</p>
    </div>
    <section v-if="isPill" class="use-section">
      <div class="section-heading">
        <h3>服用丹药</h3>
        <span class="muted">先选丹药，再选弟子</span>
      </div>
      <div v-if="pills.length" class="use-layout">
        <div class="pill-list">
          <button
            v-for="[id,count] in pills"
            :key="id"
            :class="{active:useItem===id}"
            :aria-pressed="useItem===id"
            @click="useItem=id"
          >
            <ItemIcon :id="id.split(':')[0]" />
            <span>
              {{ resourceName(id,store.catalog) }}
              <small>×{{ count }}</small>
            </span>
          </button>
        </div>
        <div class="use-detail">
          <strong>{{ resourceName(useItem,store.catalog) }}</strong>
          <p v-if="pillDefinition?.special==='heal'">一颗清除全部伤势。队伍多人受伤时，可在出征准备中一键补炼并疗伤。</p>
          <p v-else-if="pillDefinition?.special==='realm'">达到本境界等级上限后突破，所需专材可通过宗门征讨与驻守获得。</p>
          <p v-else>强化名额未满时增加效果，满额后高阶丹替换最低阶效果，只增加差额；不能提升时不会消耗丹药。</p>
          <label class="field-label">
            服用弟子
            <select v-model="useTarget" :disabled="readOnly||store.busy">
              <option value="">选择弟子</option>
              <option v-for="disciple in store.disciples" :key="disciple.id" :value="disciple.id">
                {{ discipleName(disciple.id) }}
                ·
                {{ injuryText(disciple) }}
              </option>
            </select>
          </label>
          <p v-if="target && pillDefinition?.max_uses">
            已强化
            {{ usedGrades.length }}
            /
            {{ pillDefinition.max_uses }}
            次
            <span v-if="usedGrades.length">· 品级 {{ usedGrades.join('、') }}</span>
          </p>
          <p v-if="useReason" class="craft-reason">{{ useReason }}</p>
          <button
            class="btn btn-primary craft-button"
            :disabled="store.busy||!!useReason"
            @click="store.usePill(useItem,useTarget)"
          >
            为所选弟子服用
          </button>
        </div>
      </div>
      <p v-else class="notice-box">行囊中还没有丹药，可先在上方选择配方炼制。</p>
    </section>
    <section v-else class="weapon-section">
      <div class="section-heading">
        <h3>弟子专属武器</h3>
        <span class="muted">设施开放等级上限，逐件消耗材料提升</span>
      </div>
      <div class="weapon-grid">
        <article v-for="weapon in store.weapons" :key="weapon.id" class="weapon-card">
          <div class="weapon-head">
            <ItemIcon :id="weapon.id" />
            <div>
              <strong>{{ weapon.name }}</strong>
              <small>{{ weapon.template_name }}专属 · {{ weapon.owned ? weapon.level+' 级' : '尚未锻造' }}</small>
            </div>
          </div>
          <p class="weapon-stats">
            {{ Object.entries(weapon.stats).map(([stat,value])=>effectText({stat,mode:'add_pct',value})).join(' · ') }}
          </p>
          <p v-if="weapon.owned && weapon.level<3" class="weapon-stats">
            升级后：
            {{ Object.entries(weapon.upgrade_stats).map(([stat,value])=>effectText({stat,mode:'add_pct',value})).join(' · ') }}
          </p>
          <div class="weapon-materials">
            <span v-for="(count,id) in weaponCosts(weapon)" :key="id" :class="{missing:held(id)<count}">
              <ItemIcon :id="id" :size="18" />
              {{ resourceName(id,store.catalog) }}
              {{ held(id) }}
              /
              {{ count }}
              <button v-if="held(id)<count" class="btn btn-small btn-quiet" @click="findMaterial(id)">
                {{ store.productionDestination(id).label }}
              </button>
            </span>
          </div>
          <p class="weapon-status">
            {{ weapon.equipped_by ? '已装备 · '+discipleName(weapon.equipped_by) : weapon.in_inventory ? '已存入行囊，可在弟子堂装备' : '问道 '+weapon.unlock_floor+' 层 · 弟子 '+weapon.unlock_level+' 级解锁' }}
          </p>
          <p v-if="weaponReason(weapon)" class="craft-reason">{{ weaponReason(weapon) }}</p>
          <button
            class="btn btn-small"
            :disabled="store.busy||readOnly||!(weapon.owned?weapon.upgradeable:weapon.craftable)"
            @click="weapon.owned?store.upgradeWeapon(weapon.id):store.craftWeapon(weapon.id)"
          >
            {{ weapon.owned ? weapon.level>=3 ? '已达本期上限' : weapon.level>=weapon.max_level ? '先升级炼器炉' : '升级专武' : '锻造专武' }}
          </button>
        </article>
      </div>
    </section>
    <details class="inventory-details">
      <summary>
        宗门行囊
        <span>{{ inventory.length }} 类物品</span>
      </summary>
      <div class="inventory-grid">
        <div v-for="[id,count] in inventory" :key="id">
          <span>{{ resourceName(id,store.catalog) }}</span>
          <strong>{{ number(count) }}</strong>
        </div>
      </div>
    </details>
  </div>
</template>

<style scoped>
.craft-workshop>.section-heading h3{font-size:24px;margin:5px 0}.craft-workshop h3 small{font-size:12px;color:var(--muted)}.grade-control{display:flex;gap:12px;align-items:center;margin:17px 0;font-size:12px}.grade-control select{min-width:90px}.grade-control .muted{font-size:10px}.craft-layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:18px;margin-top:18px}.recipe-list{display:flex;flex-direction:column;gap:6px}.recipe-list>button{display:flex;align-items:center;gap:10px;padding:11px;text-align:left;background:#eae6d4;border:1px solid transparent}.recipe-list>button.active{border-color:var(--jade);background:#dfe7d1}.recipe-list strong,.recipe-list small{display:block}.recipe-list strong{font:15px 'SimSun',serif}.recipe-list small{font-size:10px;color:var(--muted);margin-top:5px}.recipe-detail{padding:21px;background:#f5efdc;border:1px solid #c5b790}.recipe-head{display:flex;gap:17px;align-items:center}.recipe-head>.item-icon{width:65px;height:65px}.recipe-head h3{font-size:27px;margin:5px 0}.recipe-head p{font-size:11px;margin:0;color:var(--muted)}.recipe-effects{display:flex;flex-direction:column;gap:5px;padding:14px 0;color:var(--jade);font-size:12px}.recipe-detail>.muted{font-size:10px;line-height:1.7}.ingredient-list>div{display:flex;align-items:center;gap:7px;padding:9px 0;border-bottom:1px solid #d5c8a8;font-size:11px;flex-wrap:wrap}.ingredient-list strong{margin-left:auto;font-weight:500;color:var(--jade)}.ingredient-list .missing strong{color:var(--danger)}.ingredient-list .btn{font-size:10px;padding:4px 6px}.quantity-control{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;margin:16px 0}.quantity-control label{display:flex;gap:10px;align-items:center;font-size:12px}.quantity-control input{width:80px;min-height:36px}.craft-reason{color:var(--danger);font-size:11px;line-height:1.7;margin:12px 0 7px}.craft-button{width:100%;margin-top:12px}.use-section,.weapon-section{margin-top:28px;padding-top:20px;border-top:1px solid #c8b995}.use-section h3,.weapon-section h3{font-size:21px}.use-layout{display:grid;grid-template-columns:190px minmax(0,1fr);gap:18px}.pill-list{display:flex;flex-direction:column;gap:5px}.pill-list>button{display:flex;gap:8px;align-items:center;padding:9px;background:#eae6d4;border:1px solid transparent;text-align:left;font-size:11px}.pill-list>button.active{border-color:var(--jade);background:#dfe7d1}.pill-list span{flex:1}.pill-list small{float:right;color:var(--jade)}.use-detail{padding:18px;border:1px solid #c5b790;background:#f4ecd8}.use-detail>strong{font:20px 'SimSun',serif}.use-detail p{font-size:11px;line-height:1.8;color:var(--muted)}.use-detail p.craft-reason{color:var(--danger)}.field-label{display:block;margin:14px 0;font-size:11px}.field-label select{display:block;width:100%;margin-top:7px}.weapon-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.weapon-card{padding:14px;border:1px solid #c7b893;background:#f3edda;display:flex;flex-direction:column}.weapon-head{display:flex;align-items:center;gap:11px}.weapon-head strong,.weapon-head small{display:block}.weapon-head strong{font:17px 'SimSun',serif}.weapon-head small{font-size:10px;color:var(--muted);margin-top:5px}.weapon-stats{font-size:11px;line-height:1.8;color:var(--jade);margin:10px 0 4px}.weapon-materials{display:flex;flex-wrap:wrap;gap:5px 10px;margin:9px 0}.weapon-materials>span{display:inline-flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)}.weapon-materials>.missing{color:var(--danger)}.weapon-status{font-size:10px;color:var(--muted);line-height:1.7;margin:6px 0}.weapon-card>.btn{width:100%;margin-top:auto}.weapon-card>.craft-reason{margin:6px 0 10px}.inventory-details{margin-top:24px;border:1px solid #c8b995;background:#eee8d6}.inventory-details summary{padding:12px 15px;cursor:pointer;font-size:13px}.inventory-details summary>span{float:right;font-size:10px;color:var(--muted)}.inventory-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:0 15px 15px}.inventory-grid>div{display:flex;gap:10px;justify-content:space-between;font-size:11px;background:#e1e4d0;padding:8px}.inventory-grid strong{color:var(--jade)}@media(max-width:640px){.craft-layout,.use-layout{grid-template-columns:1fr}.recipe-list,.pill-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.recipe-list>button{padding:8px;gap:7px}.recipe-list strong{font-size:13px}.recipe-detail,.use-detail{padding:15px}.weapon-grid{grid-template-columns:1fr}.inventory-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.grade-control{flex-wrap:wrap}.grade-control .muted{width:100%}.craft-workshop>.section-heading{align-items:flex-start;gap:10px}.craft-workshop>.section-heading>.btn{font-size:10px}.use-section>.section-heading,.weapon-section>.section-heading{align-items:flex-start;flex-direction:column;gap:4px}.quantity-control{flex-wrap:wrap}}
</style>
