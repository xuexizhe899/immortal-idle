<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import ItemIcon from '../components/game/ItemIcon.vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { discipleImage } from '../presentation/assetPaths'
import { effectText,injuryText,resourceName,type DisplayCatalog } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'
import type { WeaponView } from '../api/client'

const props=defineProps<{kind?:string;readOnly?:boolean}>()
const store=useGameStore();const catalog=computed(()=>store.catalog as DisplayCatalog|null)
const selectedId=ref('');const feedback=ref('');const useItem=ref('');const useTarget=ref('');const useFeedback=ref('')
const recipes=computed(()=>Object.entries(catalog.value?.recipes??{}).filter(([,r])=>!props.kind||r.kind===props.kind))
const recipe=computed(()=>catalog.value?.recipes[selectedId.value])
const inputs=computed(()=>Object.entries(recipe.value?.inputs??{}))
const targetDisciple=computed(()=>store.disciples.find(d=>d.id===useTarget.value))
const missing=computed(()=>inputs.value.filter(([id,count])=>(store.state?.inventory?.[id]??0)<count))
const crafted=computed(()=>new Set(store.state?.crafted_recipes??[]))
const reason=computed(()=>{
  if(props.readOnly)return '出征期间仅可查阅配方，结算后可继续炼制'
  if(recipe.value?.kind==='artifact'&&crafted.value.has(selectedId.value))return '该法器已打造，无法重复炼制'
  return missing.value.length?`缺少 ${missing.value.map(([id,n])=>`${resourceName(id,catalog.value)} ${n-(store.state?.inventory?.[id]??0)}`).join('、')}`:''
})
const inventory=computed(()=>{
  const counts=new Map(Object.entries(store.state?.inventory??{}).filter(([,n])=>n>0))
  const legacy=counts.get('healing_pill')
  if(legacy){counts.delete('healing_pill');counts.set('liao_shang_dan',(counts.get('liao_shang_dan')??0)+legacy)}
  return [...counts.entries()]
})
const pills=computed(()=>Object.entries(catalog.value?.recipes??{})
  .filter(([,r])=>r.kind==='pill')
  .map(([id,r])=>({id,name:r.name,count:stockOf(id)}))
  .filter(item=>item.count>0))
const selectedPill=computed(()=>catalog.value?.recipes[useItem.value])
const useEffects=computed(()=>selectedPill.value?.effects.map(effectText).join('、')??'')
const useReason=computed(()=>{
  if(props.readOnly)return '出征期间不可服用，结算后可继续'
  if(!selectedPill.value)return '行囊中没有可服用的丹药'
  if(!useTarget.value)return '请选择服用弟子'
  const d=targetDisciple.value
  if(!d)return '弟子不存在'
  if(d.busy)return '弟子正在出征，暂不可服用'
  if(selectedPill.value.special==='heal'&&d.injury_stacks<=0)return '该弟子没有伤势'
  const limit=selectedPill.value.max_uses
  if(limit&&(d.pill_uses?.[useItem.value]??0)>=limit)return `该弟子服用已达上限（${limit} 次）`
  return ''
})
const weapons=computed(()=>store.weapons)
const showWeapons=computed(()=>!props.kind||props.kind==='artifact')
watch(recipes,list=>{selectedId.value=list[0]?.[0]??'';feedback.value=''},{immediate:true})
watch(selectedId,()=>{feedback.value=''})
watch(pills,list=>{if(!list.some(item=>item.id===useItem.value))useItem.value=list[0]?.id??''},{immediate:true})
watch(useItem,()=>{useFeedback.value=''})
onMounted(()=>{void store.loadWeapons()})

function stockOf(id:string):number{
  const base=store.state?.inventory?.[id]??0
  return id==='liao_shang_dan'?base+(store.state?.inventory?.healing_pill??0):base
}
function materialCount(id:string):number{return store.state?.inventory?.[id]??0}
function discipleName(id:string):string{
  const d=store.disciples.find(item=>item.id===id)??store.disciples.find(item=>item.template_id===id)
  return d?catalog.value?.disciples[d.template_id]?.name??id:id
}
function useDescription():string{
  if(selectedPill.value?.special==='heal')return '清除所选弟子的全部伤势，无伤时不可服用。'
  if(selectedPill.value?.special==='realm')return '境界 +1，需要达到当前境界的等级上限。'
  return useEffects.value
}
function weaponStatus(weapon:WeaponView):string{
  if(weapon.equipped_by)return `已装备 · ${discipleName(weapon.equipped_by)}`
  if(weapon.in_inventory)return '已锻造 · 在行囊'
  return weapon.reason||'可锻造'
}
function weaponStats(weapon:WeaponView):string[]{
  return Object.entries(weapon.stats).map(([stat,value])=>effectText({stat,mode:'add_pct',value}))
}
async function craft(){
  if(!recipe.value||reason.value)return
  const name=recipe.value.name;const kind=recipe.value.kind
  await store.craft(selectedId.value)
  if(!store.error)feedback.value=kind==='pill'?`${name}已炼成 1 颗，存入行囊。`:`${name}炼制完成，效果已生效。`
}
async function use(){
  if(!selectedPill.value||useReason.value)return
  const name=selectedPill.value.name
  await store.usePill(useItem.value,useTarget.value)
  if(!store.error){useFeedback.value=`${name}已服用。`;useTarget.value=''}
}
async function forge(weapon:WeaponView){
  if(!weapon.craftable)return
  await store.craftWeapon(weapon.id)
  if(!store.error)feedback.value=`${weapon.name}锻造完成，已存入行囊。`
}
</script>
<template><div class="craft-layout"><div class="recipe-list"><button v-for="[id,r] in recipes" :key="id" :class="{active:selectedId===id}" @click="selectedId=id"><span class="recipe-icon"><ItemIcon :id="id" :size="24" /></span><span><strong>{{ r.name }}</strong><small>{{ r.kind==='pill'?'丹药':'法器' }}</small></span><span class="recipe-check" v-if="Object.entries(r.inputs).every(([id,n])=>(store.state?.inventory?.[id]??0)>=n)&&!(r.kind==='artifact'&&crafted.has(id))">可炼</span></button></div><div v-if="recipe" class="recipe-detail"><div class="recipe-head"><div class="recipe-artwork"><ItemIcon :id="selectedId" :size="128" variant="display" /></div><div><span class="eyebrow">{{ props.kind==='pill'?'ALCHEMY · 丹道':'ARTIFACTS · 器道' }}</span><h3>{{ recipe.name }}</h3></div></div><div class="recipe-effects"><template v-if="recipe.special==='heal'"><strong>疗愈伤势</strong><p>炼成疗伤丹，服用时清除所选弟子的全部伤势。</p></template><template v-else-if="recipe.special==='realm'"><strong>助益破境</strong><p>炼成破境丹，服用时提升所选弟子的境界。</p></template><template v-else><strong v-for="(e,i) in recipe.effects" :key="i">{{ effectText(e) }}</strong><p v-if="recipe.kind==='pill'">炼成后存入行囊，由弟子服用后生效。</p><p v-else>宗门永久加成，炼制后立即生效。</p></template></div><h4>所需材料</h4><div class="ingredient-list"><div v-for="[id,n] in inputs" :key="id" :class="{missing:(store.state?.inventory?.[id]??0)<n}"><span class="ingredient-name"><ItemIcon :id="id" :size="22" /><span>{{ resourceName(id,catalog) }}</span></span><strong>{{ number(store.state?.inventory?.[id]) }} <small>/ {{ n }}</small></strong></div></div><p v-if="reason" class="craft-reason">{{ reason }}</p><div v-if="feedback" class="notice-box" role="status">{{ feedback }}</div><button class="btn btn-primary craft-button" :disabled="store.busy||!!reason" @click="craft"><GameIcon :name="props.kind==='pill'?'flame':'stone'" />{{ crafted.has(selectedId)?'已打造':recipe.kind==='pill'?'炼成 1 颗':'开始炼制' }}</button><p class="muted">{{ recipe.kind==='pill'?'炼制只产出丹药，不直接服用；请在下方向指定弟子服用。':'炼制后直接获得宗门永久加成，与弟子专武不同。' }}</p></div></div>
  <section v-if="!props.kind||props.kind==='pill'" class="use-section"><div class="section-heading"><h4>服用丹药</h4><span class="muted">选择一名弟子服用，每次消耗 1 颗</span></div><div class="use-layout"><div class="pill-list"><button v-for="item in pills" :key="item.id" :class="{active:useItem===item.id}" @click="useItem=item.id"><ItemIcon :id="item.id" :size="24" /><span>{{ item.name }}<small>× {{ item.count }}</small></span></button><p v-if="!pills.length" class="muted">行囊暂无丹药，先炼制一炉。</p></div><div v-if="selectedPill" class="use-detail"><strong>{{ selectedPill.name }}</strong><p>{{ useDescription() }}</p><p v-if="selectedPill.max_uses" class="hint">每名弟子最多服用 {{ selectedPill.max_uses }} 次</p><p v-if="useEffects&&selectedPill.effects.some(e=>e.stat.endsWith('_rate'))" class="hint">生产加成只在该弟子值守并提供对应产出时生效。</p><label for="use-target" class="field-label">选择服用弟子</label><select id="use-target" v-model="useTarget"><option value="">请选择弟子</option><option v-for="d in store.disciples" :key="d.id" :value="d.id" :disabled="d.busy">{{ catalog?.disciples[d.template_id]?.name }} · {{ d.busy?'出征中':`等级 ${d.level} · 境界 ${d.realm}` }}</option></select><div v-if="targetDisciple" class="target-preview"><img :src="discipleImage(targetDisciple.template_id,catalog)" alt="" class="pixel-art" /><span>{{ injuryText(targetDisciple) }} · {{ selectedPill.name }}已服用 {{ targetDisciple.pill_uses?.[useItem]??0 }}{{ selectedPill.max_uses?` / ${selectedPill.max_uses}`:'' }} 次</span></div><p v-if="useReason" class="craft-reason">{{ useReason }}</p><div v-if="useFeedback" class="notice-box" role="status">{{ useFeedback }}</div><button class="btn btn-primary craft-button" :disabled="store.busy||!!useReason" @click="use">服用{{ selectedPill.name }}</button></div></div></section>
  <section v-if="showWeapons" class="weapon-section"><div class="section-heading"><h4>专属武器</h4><span class="muted">拥有对应弟子、问道塔 8 层、弟子 3 级后可锻造</span></div><div class="weapon-grid"><article v-for="weapon in weapons" :key="weapon.id" class="weapon-card"><div class="weapon-head"><ItemIcon :id="weapon.id" :size="34" /><div><strong>{{ weapon.name }}</strong><small>{{ weapon.template_name }}专武</small></div></div><p class="weapon-stats">{{ weaponStats(weapon).join(' · ') }}</p><p class="weapon-materials"><span v-for="[id,n] in Object.entries(weapon.inputs)" :key="id" :class="{missing:materialCount(id)<n}"><ItemIcon :id="id" :size="16" />{{ resourceName(id,catalog) }} {{ materialCount(id) }}/{{ n }}</span></p><p class="weapon-status" :class="{ready:weapon.craftable}">{{ weaponStatus(weapon) }}</p><button class="btn btn-small" :disabled="store.busy||!weapon.craftable" @click="forge(weapon)">{{ weapon.owned?'已拥有':'锻造' }}</button></article><p v-if="!weapons.length" class="muted">正在读取专武图谱。</p></div></section>
  <details class="inventory-details"><summary>宗门行囊 <span>{{ inventory.length }} 种物品</span></summary><div class="inventory-grid"><div v-for="[id,n] in inventory" :key="id"><span class="inventory-name"><ItemIcon :id="id" :size="22" /><span>{{ resourceName(id,catalog) }}</span></span><strong>{{ number(n) }}</strong></div><p v-if="!inventory.length" class="muted">行囊尚空，出征问道塔可获得材料。</p></div></details><div v-if="Object.keys(store.state?.bonuses??{}).length" class="permanent-bonuses"><h4>已获得的宗门永久加成</h4><div class="chips"><span v-for="(v,key) in store.state?.bonuses" :key="key" class="badge">{{ effectText({stat:key,mode:'add_pct',value:v}) }}</span></div></div></template>
<style scoped>
.craft-layout{display:grid;grid-template-columns:200px minmax(0,1fr);gap:25px}.recipe-list{display:flex;flex-direction:column;gap:5px}.recipe-list>button{display:flex;align-items:center;gap:10px;padding:12px 10px;border:1px solid transparent;background:#ece8d7;text-align:left;min-height:65px}.recipe-list>button.active{border-color:#9cae8c;background:#e1e7d3}.recipe-icon{width:32px;height:35px;display:grid;place-items:center;color:var(--gold);background:#f7f0da;border:1px solid #d1c29b}.recipe-list strong{font-size:13px;display:block}.recipe-list small{font-size:9px;color:var(--muted)}.recipe-check{margin-left:auto;font-size:9px;color:var(--jade)}.recipe-detail{padding:22px;background:#efe9d8;border:1px solid #d0c5a5}.recipe-head .eyebrow{font-size:8px}.recipe-detail h3{font-size:27px;margin:6px 0 14px}.recipe-head{display:grid;grid-template-columns:128px minmax(0,1fr);align-items:center;gap:18px;margin-bottom:18px}.recipe-head>div:last-child{min-width:0}.recipe-artwork{display:grid;place-items:center;width:128px;height:144px;background:#e2e4d5;border:1px solid #b8c1ac;box-shadow:inset 0 0 0 5px #efe9d8}.recipe-head h3{overflow-wrap:anywhere;margin:4px 0 0}.ingredient-name{display:flex;align-items:center;gap:7px}.inventory-name{display:flex;align-items:center;gap:7px}.recipe-effects{padding:14px;border-left:2px solid #93a67c;background:#e3e7d4;margin-bottom:20px}.recipe-effects strong{display:block;font-size:13px;color:var(--jade)}.recipe-effects p{margin:4px 0 0;font-size:11px;color:var(--muted)}.recipe-detail h4{margin:0 0 10px;font-size:14px}.ingredient-list{margin-bottom:20px}.ingredient-list>div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #d8ceb4;font-size:12px}.ingredient-list strong{color:var(--jade);font-weight:500}.ingredient-list small{color:var(--muted)}.ingredient-list .missing strong{color:var(--danger)}.target-preview{display:flex;align-items:center;gap:10px;margin-top:10px;font-size:11px;color:var(--muted)}.target-preview>img{width:34px;height:40px;object-fit:cover;object-position:top}.craft-reason{color:var(--danger);font-size:11px;margin:16px 0 10px}.craft-button{width:100%;margin:14px 0}.recipe-detail>.muted{font-size:10px;margin:0}.use-section,.weapon-section{margin-top:24px;padding-top:18px;border-top:1px solid #d0c5a5}.use-section h4,.weapon-section h4{margin:0;font-size:14px}.use-layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:18px;margin-top:12px}.pill-list{display:flex;flex-direction:column;gap:5px}.pill-list>button{display:flex;align-items:center;gap:9px;padding:9px 10px;border:1px solid transparent;background:#ece8d7;text-align:left;font-size:12px}.pill-list>button.active{border-color:#9cae8c;background:#e1e7d3}.pill-list>button span{display:flex;justify-content:space-between;gap:8px;width:100%}.pill-list small{color:var(--jade)}.use-detail{padding:16px;background:#efe9d8;border:1px solid #d0c5a5}.use-detail>strong{font-size:15px}.use-detail p{margin:6px 0;font-size:11px;color:var(--muted)}.use-detail .hint{font-size:10px;color:var(--gold)}.use-detail select{width:100%}.field-label{display:block;margin:12px 0 6px;font-size:11px;color:var(--muted)}.use-detail .craft-button{margin-bottom:0}.weapon-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:12px}.weapon-card{padding:11px;background:#efe9d8;border:1px solid #d0c5a5;font-size:11px}.weapon-head{display:flex;align-items:center;gap:9px}.weapon-head strong{display:block;font-size:13px}.weapon-head small{color:var(--muted);font-size:9px}.weapon-stats{margin:8px 0;color:var(--jade)}.weapon-materials{display:flex;flex-wrap:wrap;gap:4px 10px;margin:0 0 8px;color:var(--muted);font-size:10px}.weapon-materials span{display:inline-flex;align-items:center;gap:4px}.weapon-materials .missing{color:var(--danger)}.weapon-status{margin:0 0 8px;font-size:10px;color:var(--muted)}.weapon-status.ready{color:var(--jade)}.weapon-card .btn{width:100%}.inventory-details{margin-top:24px;border:1px solid #d0c5a5;background:#eee9da}.inventory-details summary{cursor:pointer;padding:12px 16px;font-size:13px}.inventory-details summary span{float:right;font-size:11px;color:var(--muted)}.inventory-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;padding:0 16px 16px}.inventory-grid>div{display:flex;justify-content:space-between;padding:8px 10px;background:#e4e3d2;font-size:11px}.inventory-grid strong{color:var(--jade)}.permanent-bonuses{padding-top:20px}.permanent-bonuses h4{font-size:13px;margin-bottom:10px}
@media(max-width:640px){.craft-layout{grid-template-columns:1fr;gap:14px}.recipe-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.recipe-list>button{padding:8px;gap:7px;min-height:60px}.recipe-list strong{font-size:12px}.recipe-icon{width:25px;height:29px}.recipe-detail{padding:17px}.recipe-head{gap:12px}.recipe-head h3{font-size:23px}.inventory-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.recipe-check{font-size:8px}.use-layout{grid-template-columns:1fr;gap:10px}.pill-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.weapon-grid{grid-template-columns:1fr}.use-detail,.weapon-card{padding:12px}}
</style>
