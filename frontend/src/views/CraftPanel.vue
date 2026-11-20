<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import ItemIcon from '../components/game/ItemIcon.vue'
import PanelModal from '../components/ui/PanelModal.vue'
import type { RecipeView, WeaponView } from '../api/client'
import { effectText, injuryText, resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import EquipmentPanel from './EquipmentPanel.vue'

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
const section = ref('primary')
const workshop = ref<HTMLElement | null>(null)
const recipeOpen = ref(false)
const weaponId = ref('')
const selectedWeapon = computed(() => store.weapons.find(item => item.id === weaponId.value))
let previewRequest = 0
const recipes = computed(() => previews.value.filter(recipe => recipe.kind === 'pill' && (!props.kind || recipe.kind === props.kind)))
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
watch([grade, () => props.kind, () => store.revision, () => store.slotId], async (values, previous) => {
  const request = ++previewRequest
  if (!isPill.value) { previews.value = []; loading.value = false; return }
  if (values[0] !== previous[0] || values[1] !== previous[1] || values[3] !== previous[3]) {
    recipeOpen.value = false
    previews.value = []
  }
  loading.value = true
  const result = await store.previewRecipes(grade.value)
  if (request !== previewRequest) return
  previews.value = result?.recipes ?? []
  loading.value = false
  if (!recipes.value.some(item => item.id === selectedId.value)) { recipeOpen.value = false; selectedId.value = '' }
}, { immediate: true })
watch([() => props.kind, () => store.slotId], () => {
  section.value = 'primary'; recipeOpen.value = false; weaponId.value = ''; useTarget.value = ''
})
watch(section, () => {
  recipeOpen.value = false; weaponId.value = ''
  nextTick(() => workshop.value?.scrollIntoView({ block: 'start' }))
})
watch(selectedWeapon, value => { if (!value) weaponId.value = '' })
watch([selectedId, grade], () => { quantity.value = 1 })
watch(maxGrade, limit => {
  if (grade.value > limit) grade.value = 1
})
watch(pills, list => {
  if (!list.some(([id]) => id === useItem.value)) useItem.value = list[0]?.[0] ?? ''
}, { immediate: true })
watch([() => props.kind, () => store.revision, () => store.slotId], () => { if (!isPill.value) void store.loadWeapons() }, { immediate: true })
function held(id: string) { return store.state?.inventory[id] ?? 0 }
function findMaterial(id: string) {
  recipeOpen.value = false
  weaponId.value = ''
  emit('open', store.planProduction(id))
}
function openRecipe(id: string) {
  if (!recipes.value.some(item => item.id === id)) return
  selectedId.value = id
  recipeOpen.value = true
}
function openWeapon(id: string) { weaponId.value = id }
function discipleName(id: string) {
  const disciple = store.disciples.find(d => d.id === id)
  return disciple ? store.catalog?.disciples[disciple.template_id]?.name ?? id : id
}
function weaponCosts(weapon: WeaponView) { return weapon.owned ? weapon.upgrade_inputs : weapon.inputs }
function weaponReason(weapon: WeaponView) {
  if (props.readOnly) return '出征结束后可继续锻造'
  return weapon.owned ? weapon.upgrade_reason : weapon.reason
}
function recipeEffectText(item: RecipeView) {
  const special = store.catalog?.recipes[item.id]?.special
  if (special === 'heal') return '清除目标全部伤势'
  if (special === 'realm') return '达到等级上限后，用于突破境界'
  return item.effects.map(effect => effectText(effect)).join(' · ')
}
async function craft() {
  if (!isPill.value || !recipe.value || reason.value) return
  await store.craft(recipe.value.id, quantity.value, recipe.value.grade)
}
</script>

<template>
  <div ref="workshop" class="craft-workshop" :class="{alchemy:isPill,forge:!isPill}">
    <div class="section-heading">
      <div class="workshop-heading">
        <span class="workshop-seal" aria-hidden="true">{{ isPill ? '丹' : '器' }}</span>
        <div>
          <span class="eyebrow">{{ isPill ? '炉火温养 · 因材炼丹' : '百炼成器 · 以器助道' }}</span>
          <h3>
            {{ isPill ? '炼丹房' : '炼器阁' }}
            <small>{{ store.state?.facility_levels[isPill?'alchemy':'forge'] ?? 1 }} 级</small>
          </h3>
        </div>
      </div>
      <button class="btn btn-small btn-quiet" @click="emit('open','sect')">查看设施升级</button>
    </div>
    <nav class="workshop-tabs" :aria-label="isPill?'炼丹房栏目':'炼器阁栏目'">
      <button :class="{active:section==='primary'}" :aria-pressed="section==='primary'" @click="section='primary'">{{ isPill?'炼制丹药':'普通装备' }}</button>
      <button :class="{active:section==='secondary'}" :aria-pressed="section==='secondary'" @click="section='secondary'">{{ isPill?'服用丹药':'弟子专武' }}</button>
      <button :class="{active:section==='inventory'}" :aria-pressed="section==='inventory'" @click="section='inventory'">宗门行囊</button>
    </nav>
    <EquipmentPanel v-if="!isPill&&section==='primary'" :read-only="readOnly" @open="emit('open',$event)" />
    <template v-if="isPill&&section==='primary'">
    <label class="grade-control">
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
          aria-haspopup="dialog"
          @click="openRecipe(item.id)"
        >
          <ItemIcon :id="item.id" />
          <span class="recipe-copy">
            <strong>{{ item.name }}</strong>
            <span class="recipe-preview">{{ recipeEffectText(item) }}</span>
            <small>
              {{ item.grade }}品 · 库存 {{ item.stock }}
            </small>
          </span>
          <span class="recipe-quantity" :class="{ready:item.max_quantity>0}"><strong>{{ item.max_quantity }}</strong><small>可炼</small></span>
        </button>
      </div>
      <p v-if="!recipes.length" class="notice-box">暂无可用配方，请刷新进度后重试。</p>
    </div>
    </template>
    <PanelModal v-if="recipeOpen&&recipe" :title="recipe.name" subtitle="炼制丹药" @close="recipeOpen=false">
      <article class="recipe-detail">
        <div class="recipe-head">
          <ItemIcon :id="recipe.id" variant="display" />
          <div>
            <span class="eyebrow">{{ recipe.grade }}品丹方</span>
            <h3>{{ recipe.name }}</h3>
            <p>
              本次炼制 {{ quantity }} 颗
            </p>
          </div>
        </div>
        <div class="recipe-effects">
          <span v-for="(effect,index) in recipe.effects" :key="index">{{ effectText(effect) }}</span>
          <span v-if="store.catalog?.recipes[recipe.id]?.special==='heal'">清除目标全部伤势</span>
          <span v-if="store.catalog?.recipes[recipe.id]?.special==='realm'">达到当前境界等级上限后，境界提升一重</span>
        </div>
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
        <div class="quantity-control">
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
          炼制 {{ quantity }} 颗
        </button>
      </article>
    </PanelModal>
    <section v-if="isPill&&section==='secondary'" class="use-section">
      <div class="section-heading">
        <h3>服用丹药</h3>
        <span class="muted">先选丹药，再选弟子</span>
      </div>
      <div v-if="pills.length" class="use-layout">
        <div class="use-detail">
          <label class="field-label">选择丹药<select v-model="useItem" :disabled="store.busy"><option v-for="[id,count] in pills" :key="id" :value="id">{{ resourceName(id,store.catalog) }} ×{{ count }}</option></select></label>
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
      <div v-else class="notice-box workshop-empty"><p>行囊中还没有丹药，可在“炼制丹药”中选择配方炼制。</p><button class="btn btn-small" @click="section='primary'">选择丹方</button></div>
    </section>
    <section v-if="!isPill&&section==='secondary'" class="weapon-section">
      <div class="section-heading">
        <h3>弟子专属武器</h3>
        <span class="muted">设施开放等级上限，逐件消耗材料提升</span>
      </div>
      <div class="weapon-grid">
        <button v-for="weapon in store.weapons" :key="weapon.id" class="weapon-card weapon-choice" :class="{owned:weapon.owned}" aria-haspopup="dialog" @click="openWeapon(weapon.id)">
          <div class="weapon-head">
            <ItemIcon :id="weapon.id" />
            <div>
              <strong>{{ weapon.name }}</strong>
              <small>{{ weapon.template_name }}专属 · {{ weapon.owned ? weapon.level+' 级' : '尚未锻造' }}</small>
            </div>
          </div>
          <span class="weapon-status">{{ weapon.equipped_by?'已装备 · '+discipleName(weapon.equipped_by):weapon.owned?'已拥有':'尚未成器' }}<span class="weapon-open">{{ weapon.owned?'查看提升':'查看锻造条件' }}</span></span>
        </button>
      </div>
    </section>
    <PanelModal v-if="selectedWeapon" :title="selectedWeapon.name" subtitle="弟子专武 · 锻造与提升" @close="weaponId=''">
      <article v-for="weapon in [selectedWeapon]" :key="weapon.id" class="weapon-card">
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
            {{ weapon.owned ? weapon.level>=3 ? '已达本期上限' : weapon.level>=weapon.max_level ? '先升级炼器阁' : '升级专武' : '锻造专武' }}
          </button>
        </article>
    </PanelModal>
    <section v-if="section==='inventory'" class="inventory-details" aria-label="宗门行囊">
      <div class="section-heading"><h3>宗门行囊</h3><span class="muted">{{ inventory.length }} 类物品</span></div>
      <div class="inventory-grid">
        <div v-for="[id,count] in inventory" :key="id">
          <ItemIcon :id="id" :size="26" /><span>{{ resourceName(id,store.catalog) }}</span>
          <strong>{{ number(count) }}</strong>
        </div>
      </div>
      <div v-if="!inventory.length" class="notice-box workshop-empty"><p>行囊中暂无物品。挂机可积累基础材料，历练还可带回装备与战利品。</p><button class="btn btn-small" @click="emit('open','expedition')">前往山河</button></div>
    </section>
  </div>
</template>

<style scoped>
.workshop-tabs{display:flex;gap:5px;flex-wrap:wrap;margin:17px 0;padding-bottom:10px;border-bottom:1px solid var(--border)}.workshop-tabs button{flex:1;min-height:38px;padding:7px 10px;border:1px solid transparent;background:transparent;color:var(--muted);font-size:12px}.workshop-tabs button.active{border-color:#9caf8b;background:#e0e7d1;color:var(--jade)}
.craft-workshop>.section-heading h3{font-size:24px;margin:5px 0}.craft-workshop h3 small{font-size:12px;color:var(--muted)}.grade-control{display:flex;gap:12px;align-items:center;margin:17px 0;font-size:12px}.grade-control select{min-width:90px}.grade-control .muted{font-size:10px}.craft-layout{margin-top:18px}.recipe-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.recipe-list>button{min-width:0;display:flex;align-items:center;gap:10px;padding:11px;text-align:left;background:#eae6d4;border:1px solid transparent}.recipe-list>button.active{border-color:var(--jade);background:#dfe7d1}.recipe-list strong,.recipe-list small{display:block}.recipe-list strong{overflow-wrap:anywhere;font:15px 'SimSun',serif}.recipe-list small{font-size:10px;color:var(--muted);margin-top:5px}.recipe-detail{padding:21px;background:#f5efdc;border:1px solid #c5b790}.recipe-head{display:flex;gap:17px;align-items:center}.recipe-head>.item-icon{width:65px;height:65px}.recipe-head h3{font-size:27px;margin:5px 0}.recipe-head p{font-size:11px;margin:0;color:var(--muted)}.recipe-effects{display:flex;flex-direction:column;gap:5px;padding:14px 0;color:var(--jade);font-size:12px}.recipe-detail>.muted{font-size:10px;line-height:1.7}.ingredient-list>div{display:flex;align-items:center;gap:7px;padding:9px 0;border-bottom:1px solid #d5c8a8;font-size:11px;flex-wrap:wrap}.ingredient-list strong{margin-left:auto;font-weight:500;color:var(--jade)}.ingredient-list .missing strong{color:var(--danger)}.ingredient-list .btn{font-size:10px;padding:4px 6px}.quantity-control{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;margin:16px 0}.quantity-control label{display:flex;gap:10px;align-items:center;font-size:12px}.quantity-control input{width:80px;min-height:36px}.craft-reason{color:var(--danger);font-size:11px;line-height:1.7;margin:12px 0 7px}.craft-button{width:100%;margin-top:12px}.use-section,.weapon-section{margin-top:18px}.use-section h3,.weapon-section h3{font-size:21px}.use-layout{max-width:640px}.use-detail{padding:18px;border:1px solid #c5b790;background:#f4ecd8}.use-detail>strong{font:20px 'SimSun',serif}.use-detail p{font-size:11px;line-height:1.8;color:var(--muted)}.use-detail p.craft-reason{color:var(--danger)}.field-label{display:block;margin:14px 0;font-size:11px}.field-label select{display:block;width:100%;margin-top:7px}.weapon-grid{max-height:440px;overflow-y:auto;overscroll-behavior:contain;padding:1px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.weapon-card{text-align:left;min-width:0;padding:14px;border:1px solid #c7b893;background:#f3edda;display:flex;flex-direction:column}.weapon-choice{cursor:pointer}.weapon-choice:hover,.weapon-choice:focus-visible{border-color:var(--jade)}.weapon-head{display:flex;align-items:center;gap:11px}.weapon-head>div{min-width:0}.weapon-head strong,.weapon-head small{display:block}.weapon-head strong{overflow-wrap:anywhere;font:17px 'SimSun',serif}.weapon-head small{font-size:10px;color:var(--muted);margin-top:5px}.weapon-stats{font-size:11px;line-height:1.8;color:var(--jade);margin:10px 0 4px}.weapon-materials{display:flex;flex-wrap:wrap;gap:5px 10px;margin:9px 0}.weapon-materials>span{display:inline-flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)}.weapon-materials>.missing{color:var(--danger)}.weapon-status{font-size:10px;color:var(--muted);line-height:1.7;margin:6px 0}.weapon-card>.btn{width:100%;margin-top:auto}.weapon-card>.craft-reason{margin:6px 0 10px}.inventory-details{margin-top:18px}.inventory-details>.section-heading{margin-bottom:12px}.inventory-details h3{font-size:20px}.inventory-details .muted{font-size:11px}.inventory-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;max-height:420px;overflow-y:auto;overscroll-behavior:contain;padding:1px}.inventory-grid>div{display:flex;gap:10px;justify-content:space-between;font-size:11px;background:#e1e4d0;padding:8px}.inventory-grid strong{color:var(--jade)}@media(max-width:640px){.recipe-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.recipe-list>button{padding:8px;gap:7px}.recipe-list strong{font-size:13px}.recipe-detail,.use-detail{padding:15px}.weapon-grid{grid-template-columns:1fr}.inventory-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.grade-control{flex-wrap:wrap}.grade-control .muted{width:100%}.craft-workshop>.section-heading{align-items:flex-start;gap:10px}.craft-workshop>.section-heading>.btn{font-size:10px}.use-section>.section-heading,.weapon-section>.section-heading{align-items:flex-start;flex-direction:column;gap:4px}.quantity-control{flex-wrap:wrap}.workshop-tabs button{min-height:44px}.recipe-head h3{font-size:24px}.recipe-effects,.craft-reason,.ingredient-list>div,.use-detail p,.field-label,.weapon-stats,.weapon-materials>span,.weapon-status{font-size:12px}.inventory-grid>div{flex-wrap:wrap;font-size:12px}.weapon-card>.btn,.craft-button{min-height:44px}.quantity-control input,.field-label select{min-height:44px}}
.craft-workshop{--workshop-ink:#326c55;--workshop-tint:#e5ecd8;--workshop-line:#a6b795}.craft-workshop.alchemy{--workshop-ink:#7d6337;--workshop-tint:#efe7ce;--workshop-line:#c2b383}.workshop-heading{display:flex;align-items:center;gap:13px;min-width:0}.workshop-heading>div{min-width:0}.workshop-seal{width:53px;height:58px;flex:none;display:grid;place-items:center;border:1px solid var(--workshop-line);background:var(--workshop-tint);box-shadow:inset 0 0 0 4px #f6f1df,inset 0 0 0 5px var(--workshop-line);font:32px 'SimSun',serif;color:var(--workshop-ink)}.workshop-heading .eyebrow{font-size:10px;letter-spacing:.06em;color:var(--workshop-ink)}.craft-workshop>.section-heading{padding-bottom:15px;border-bottom:1px solid #d0cfb4}.craft-workshop>.section-heading h3{font-size:25px;color:#213f36;margin:5px 0 0}.craft-workshop h3 small{margin-left:6px;font-variant-numeric:tabular-nums}.workshop-tabs{margin:13px 0;gap:4px}.workshop-tabs button.active{background:var(--workshop-tint);border-color:var(--workshop-line);color:var(--workshop-ink);box-shadow:inset 0 -2px var(--workshop-ink)}.grade-control{padding:10px 12px;background:#f1edda;border-left:2px solid var(--workshop-line);margin:14px 0}.grade-control select{min-width:75px;background:#f6f1df}.craft-layout{margin-top:12px}.recipe-list{gap:8px;max-height:min(50dvh,460px);overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding:1px}.recipe-list>button{position:relative;align-items:flex-start;gap:10px;min-height:110px;padding:12px;border:1px solid #cdc7a9;background:#f6f1df}.recipe-list>button.active{border-color:var(--workshop-ink);background:#f0ead5;box-shadow:inset 0 3px var(--workshop-line)}.recipe-list>button>.item-icon{margin-top:3px}.recipe-copy{min-width:0;flex:1}.recipe-list strong{color:#3f4b32;font-size:16px}.recipe-list .recipe-preview{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:11px;line-height:1.7;color:#786b4e;margin-top:6px;min-height:2.5em}.recipe-list small{margin-top:6px}.recipe-quantity{display:flex;flex-direction:column;align-items:center;flex:none;min-width:25px;padding-left:8px;border-left:1px solid #ded7bd;color:#9a927a}.recipe-list .recipe-quantity>strong{font:24px 'SimSun',serif;color:inherit;font-variant-numeric:tabular-nums}.recipe-list .recipe-quantity>small{font-size:9px;color:inherit;margin-top:3px}.recipe-quantity.ready{color:#326c55}.recipe-detail{border-color:#c0b17f;background:#f6f1df;border-top:3px solid #b38a46}.recipe-effects{border-bottom:1px solid #dad4b9;margin-bottom:7px;color:#71602f}.recipe-head .eyebrow{color:#8c6844;font-size:10px;letter-spacing:.06em}.recipe-head h3{color:#213f36}.use-detail{border-top:3px solid #b38a46;background:#f6f1df}.weapon-grid{gap:9px}.weapon-choice{border-color:#c2c8ac;background:#f6f1df;border-left:3px solid #b6b99c;padding:13px}.weapon-choice.owned{border-left-color:#326c55;background:#eef1df}.weapon-head strong{font-size:16px;color:#213f36}.weapon-choice .weapon-status{display:flex;align-items:center;gap:8px;justify-content:space-between;padding-top:9px;margin:9px 0 0;border-top:1px solid #d6dac0;line-height:1.6}.weapon-open{flex:none;color:#326c55;border-bottom:1px solid #9bad8e;padding-bottom:1px}.weapon-card:not(.weapon-choice){background:#f6f1df;border-top:3px solid #7a9a7d}.inventory-grid{gap:0;border-top:1px solid #c7cfb3}.inventory-grid>div{align-items:center;justify-content:flex-start;gap:8px;background:#f1f0df;padding:10px 8px;border-right:1px solid #d5d9c0;border-bottom:1px solid #d5d9c0;min-width:0}.inventory-grid>div>span:not(.item-icon){flex:1;min-width:0;overflow-wrap:anywhere}.inventory-grid strong{font-variant-numeric:tabular-nums;margin-left:auto}.workshop-empty p{font-size:12px;line-height:1.8;margin:0 0 12px}.craft-workshop button:focus-visible{outline:2px solid #326c55;outline-offset:2px}
@media(max-width:640px){.workshop-heading{gap:10px}.workshop-seal{width:43px;height:51px;font-size:28px}.workshop-heading .eyebrow{font-size:9px;letter-spacing:0}.craft-workshop>.section-heading h3{font-size:22px}.craft-workshop>.section-heading>.btn{max-width:80px;min-height:44px;white-space:normal;font-size:11px;padding-inline:6px}.recipe-list{gap:6px;max-height:min(50dvh,410px)}.recipe-list>button{flex-wrap:wrap;gap:7px;min-height:150px;padding:9px}.recipe-list>button>.item-icon{width:27px!important;height:27px!important;flex-basis:27px}.recipe-list strong{font-size:15px}.recipe-list .recipe-preview{font-size:11px;min-height:3.4em;line-height:1.7}.recipe-list small{font-size:10px}.recipe-quantity{width:100%;flex-direction:row;justify-content:flex-end;gap:5px;border-left:0;border-top:1px solid #ded7bd;padding:5px 0 0;margin-top:auto}.recipe-list .recipe-quantity>strong{font-size:20px}.recipe-list .recipe-quantity>small{font-size:10px;margin:0}.grade-control{gap:8px;font-size:12px;padding:9px 10px}.grade-control select{min-height:44px}.grade-control .muted{font-size:11px}.weapon-choice .weapon-status{font-size:11px;flex-wrap:wrap}.weapon-head strong{font-size:17px}.inventory-grid>div{flex-wrap:nowrap;font-size:11px;padding:10px 7px;gap:6px}.inventory-grid>div>.item-icon{width:23px!important;height:23px!important;flex-basis:23px}.inventory-grid>div>strong{font-size:12px}.workshop-empty>.btn{min-height:44px}}
</style>
<style scoped>
.craft-workshop{--workshop-ink:var(--jade);--workshop-tint:var(--jade-light);--workshop-line:var(--jade-deep)}
.craft-workshop.alchemy{--workshop-ink:var(--gold);--workshop-tint:#3d3220;--workshop-line:var(--gold-deep)}
.workshop-tabs{border-color:var(--line-faint)}.workshop-tabs button{color:var(--muted)}.workshop-tabs button.active{background:var(--workshop-tint);border-color:var(--workshop-line);color:var(--workshop-ink);box-shadow:inset 0 -2px var(--workshop-ink)}
.workshop-seal{border-color:var(--workshop-line);background:var(--workshop-tint);box-shadow:inset 0 0 0 4px var(--surface),inset 0 0 0 5px var(--workshop-line);color:var(--workshop-ink)}
.craft-workshop>.section-heading{border-color:var(--line-faint)}.craft-workshop>.section-heading h3{color:var(--ink)}.workshop-heading .eyebrow{color:var(--workshop-ink)}
.grade-control{background:var(--surface-inset);border-left-color:var(--workshop-line)}.grade-control select{background:var(--surface-raised)}
.recipe-list>button{background:var(--surface-inset);border-color:var(--border)}.recipe-list>button.active{border-color:var(--workshop-ink);background:var(--surface-raised);box-shadow:inset 0 3px var(--workshop-line)}.recipe-list strong{color:var(--ink)}.recipe-list .recipe-preview{color:var(--muted)}.recipe-quantity{border-color:var(--line-faint);color:var(--muted)}.recipe-quantity.ready{color:var(--jade)}
.recipe-detail,.use-detail,.weapon-card,.weapon-choice,.inventory-grid>div,.production-panel,.assignment-panel{background:var(--surface-inset);border-color:var(--border)}.recipe-detail,.use-detail{border-top-color:var(--gold-deep)}.recipe-head h3,.use-detail>strong,.weapon-head strong{color:var(--ink)}.recipe-effects{border-color:var(--line-faint);color:var(--jade)}.ingredient-list>div{border-color:var(--line-faint)}.weapon-choice{border-left-color:var(--border)}.weapon-choice.owned{border-left-color:var(--jade);background:var(--surface-raised)}.weapon-choice .weapon-status{border-color:var(--line-faint)}
.inventory-grid{border-color:var(--border)}.inventory-grid>div{border-color:var(--line-faint)}.inventory-grid strong,.weapon-stats{color:var(--jade)}.production-panel,.assignment-panel{border-top-color:var(--jade-deep)}
.craft-workshop button:focus-visible{outline-color:var(--gold)}
@media(max-width:640px){.recipe-list>button{min-height:142px}.recipe-list .recipe-quantity{border-color:var(--line-faint)} }
</style>
