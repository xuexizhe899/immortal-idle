<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import PartyHealing from '../components/game/PartyHealing.vue'
import { characterImage, discipleImage } from '../presentation/assetPaths'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

const props = defineProps<{ focused?: boolean }>()
defineEmits<{ edit: [] }>()
const store = useGameStore()
const panel = ref<HTMLElement | null>(null)
const detailsOpen = ref(false)
const detailTab = ref<'garrison' | 'retrial' | 'prepare' | 'intel'>('prepare')
const selectedId = computed({
  get: () => store.targetSectId,
  set: (id: string) => { store.targetSectId = id },
})
const recruitId = ref('')
const filter = ref('all')
const sects = computed(() => store.state?.sects.filter(sect => (sect.region_id ?? 1) === (store.state?.world?.current_region ?? 1)) ?? [])
const areaReason = computed(() => selected.value && selected.value.area > (store.state?.world?.unlocked_areas[String(store.state.world.current_region)] ?? 1) ? '请先击败前一片区的守关首领' : '')
const visible = computed(() => sects.value.filter(sect =>
  filter.value === 'all' || (filter.value === 'conquered' ? sect.conquered : !sect.conquered),
))
const selected = computed(() => sects.value.find(sect => sect.id === selectedId.value))
const detailTabs = computed(() => selected.value?.conquered
  ? [{ id: 'garrison' as const, label: '驻守经营' }, { id: 'retrial' as const, label: '宗主论道' }]
  : [{ id: 'prepare' as const, label: '出征整备' }, { id: 'intel' as const, label: '敌方情报' }])
const party = computed(() => store.party.map(id => store.disciples.find(d => d.id === id)).filter(d => !!d))
const resourceGoal = computed(() => {
  const resourceId = store.productionTarget
  if (!resourceId || !selected.value) return ''
  if (selected.value.material_id !== resourceId && selected.value.special_material_id !== resourceId) return ''
  const material = resourceName(resourceId, store.catalog)
  return selected.value.conquered
    ? `当前需要${material}。该宗门已攻克，安排弟子驻守即可持续获取。`
    : `当前需要${material}。先攻克这座宗门，获得战利品后即可派遣弟子驻守。`
})
const cost = computed(() => store.catalog?.modes.expedition?.stamina_cost ?? 2)
const retrialReward = computed(() => store.worldMap?.regions
  .find(region => region.id === (selected.value?.region_id ?? 1))?.nodes
  .find(node => node.sect_id === selected.value?.id)?.retrial_rewards ?? {})
const retrialReason = computed(() => {
  if (areaReason.value) return areaReason.value
  if (store.state?.active_run) return '已有进行中的出征，请先完成或结算'
  if (party.value.length < 3) return '至少需要三位随行弟子，最多可带六人轮换'
  if (party.value.some(d => d.busy)) return '队伍中有正在出征的弟子'
  return (store.resources?.stamina ?? 0) < cost.value ? '行动力不足，先收取宗门收益再来' : ''
})
const reason = computed(() => {
  if (areaReason.value) return areaReason.value
  if (store.state?.active_run) return '已有进行中的出征，请先完成或结算'
  if (!selected.value || selected.value.conquered) return '请选择尚未攻克的宗门'
  if (party.value.length < 3) return '至少需要三位随行弟子，最多可带六人轮换'
  if (party.value.some(d => d.busy)) return '队伍中有正在出征的弟子'
  return (store.resources?.stamina ?? 0) < cost.value ? '行动力不足，先收取宗门收益再来' : ''
})
const candidates = computed(() => store.disciples
  .filter(d => !d.busy && !selected.value?.garrison.some(slot => slot.disciple_id === d.id))
  .sort((a, b) => Number(matches(b.template_id)) - Number(matches(a.template_id))),
)
watch([sects, () => props.focused], ([list, focused]) => {
  if (!focused && !list.some(sect => sect.id === selectedId.value)) selectedId.value = list[0]?.id ?? ''
}, { immediate: true })
watch([() => selected.value?.id, () => selected.value?.conquered], () => {
  recruitId.value = ''
  detailTab.value = selected.value?.conquered ? 'garrison' : 'prepare'
  if (!selected.value) detailsOpen.value = false
}, { immediate: true })
function focusSection(selector: string) {
  nextTick(() => {
    panel.value?.closest<HTMLElement>('.modal-body')?.scrollTo({ top: 0, behavior: 'auto' })
    const active = panel.value?.querySelector<HTMLButtonElement>(selector)
    active?.focus({ preventScroll: true })
    active?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' })
  })
}
function openSect(id: string) {
  if (!sects.value.some(sect => sect.id === id)) return
  selectedId.value = id
  detailsOpen.value = true
  focusSection('.sect-detail-tabs [aria-pressed="true"]')
}
function closeDetails() { detailsOpen.value = false; focusSection('.sect-marker.selected') }
function selectDetailTab(id: typeof detailTab.value) {
  detailTab.value = id
  focusSection('.sect-detail-tabs [aria-pressed="true"]')
}
function matches(templateId: string) {
  const specialty = store.catalog?.disciples[templateId]?.production_specialty
  return specialty === selected.value?.material_id || specialty === selected.value?.special_material_id
}
function name(id: string) {
  const disciple = store.disciples.find(d => d.id === id)
  return disciple ? store.catalog?.disciples[disciple.template_id]?.name ?? id : id
}
function templateId(id: string) { return store.disciples.find(d => d.id === id)?.template_id ?? '' }
function post(id: string) {
  if (store.state?.duty_slots.some(slot => slot.disciple_id === id)) return '本宗值守'
  return store.state?.sects.find(sect => sect.garrison.some(slot => slot.disciple_id === id))?.name ?? '待安排'
}
async function assign() {
  if (!selected.value || !recruitId.value) return
  await store.assignGarrison(selected.value.id, recruitId.value)
  if (!store.error) recruitId.value = ''
}
</script>

<template>
  <div ref="panel" class="expedition-panel">
  <section v-if="!focused && !detailsOpen" class="expedition-charter">
    <header class="charter-heading">
      <div>
        <span class="eyebrow">山外有山 · 宗门征讨</span>
        <h3>择一山门，携同道而往</h3>
        <p class="muted">攻破守备，挑战宗主；凯旋后可派弟子驻守，持续收取当地资源。</p>
      </div>
      <span class="charter-seal">征</span>
    </header>
    <div class="territory-overview">
      <span>
        已发现
        <strong>{{ sects.length }}</strong>
        座宗门
      </span>
      <span>
        已攻克
        <strong>{{ sects.filter(sect=>sect.conquered).length }}</strong>
        座
      </span>
      <span>
        主殿
        <strong>{{ store.state?.facility_levels.hall ?? 1 }}</strong>
        级
      </span>
    </div>
    <div class="tabs" aria-label="宗门筛选">
      <button :class="{active:filter==='all'}" @click="filter='all'">全部山门</button>
      <button :class="{active:filter==='available'}" @click="filter='available'">待征讨</button>
      <button :class="{active:filter==='conquered'}" @click="filter='conquered'">驻守领地</button>
    </div>
    <div class="sect-map" tabindex="0" aria-label="选择宗门">
      <button
        v-for="sect in visible"
        :key="sect.id"
        class="sect-marker"
        :class="{selected:sect.id===selectedId,conquered:sect.conquered}"
        :aria-pressed="sect.id===selectedId"
        @click="openSect(sect.id)"
      >
        <span class="marker-level">{{ sect.level }} 阶</span>
        <strong>{{ sect.name }}</strong>
        <small>{{ sect.style }}</small>
        <span class="resource-line">
          {{ resourceName(sect.material_id,store.catalog) }}
          ·
          {{ resourceName(sect.special_material_id,store.catalog) }}
        </span>
        <span class="marker-status">{{ sect.conquered ? '已攻克 · 驻守 '+sect.garrison.length+'/3' : '守备 100 · 待征讨' }}</span>
      </button>
    </div>
    <p v-if="!visible.length" class="notice-box">{{ sects.length ? '此处还没有宗门。可切换筛选查看其他山门。' : '正在整理远行宗门，刷新进度后可查看。' }}</p>
  </section>
    <article v-if="selected && (focused || detailsOpen)" class="sect-dossier" :class="{focused}">
      <button v-if="!focused" class="btn btn-small btn-quiet back-to-sects" @click="closeDetails">返回宗门列表</button>
      <p v-if="resourceGoal" class="notice-box">{{ resourceGoal }}</p>
      <div class="section-heading">
        <div>
          <span class="eyebrow">{{ selected.conquered ? '驻守经营' : '战前情报' }}</span>
          <h3>{{ selected.name }}</h3>
        </div>
        <span class="badge badge-gold">{{ selected.style }} · {{ selected.level }} 阶</span>
      </div>
      <nav class="sect-detail-tabs" aria-label="宗门详情栏目"><button v-for="item in detailTabs" :key="item.id" :class="{active:detailTab===item.id}" :aria-pressed="detailTab===item.id" @click="selectDetailTab(item.id)">{{ item.label }}</button></nav>
      <template v-if="detailTab==='garrison'">
        <p class="muted">每人独立贡献产出，专长匹配时收益更高；离岗暂停该弟子的贡献，空岗不产出。</p>
        <div class="garrison-production">
          <span v-for="(amount,id) in store.production.garrisons?.[selected.id]" :key="id">
            {{ resourceName(id,store.catalog) }}
            <strong>+{{ number(amount,2) }}/时</strong>
          </span>
          <span v-if="!selected.garrison.length" class="muted">尚未派人驻守</span>
        </div>
        <div class="garrison-list">
          <div v-for="slot in selected.garrison" :key="slot.disciple_id">
            <img
              :src="discipleImage(templateId(slot.disciple_id),store.catalog)"
              alt=""
              class="pixel-art"
              loading="lazy"
            />
            <span>
              <strong>{{ name(slot.disciple_id) }}</strong>
              <small>
                专长 ·
                {{ resourceName(store.catalog?.disciples[templateId(slot.disciple_id)]?.production_specialty ?? '',store.catalog) }}
              </small>
            </span>
            <button
              class="btn btn-small"
              :disabled="store.busy"
              @click="store.unassignGarrison(selected.id,slot.disciple_id)"
            >
              召回
            </button>
          </div>
        </div>
        <div v-if="selected.garrison.length<3" class="garrison-form">
          <label>
            派遣弟子
            <select v-model="recruitId" :disabled="store.busy">
              <option value="">选择弟子 · 匹配专长优先</option>
              <option v-for="disciple in candidates" :key="disciple.id" :value="disciple.id">
                {{ name(disciple.id) }}
                {{ matches(disciple.template_id) ? ' · 专长匹配' : '' }}
                ·
                {{ post(disciple.id) }}
              </option>
            </select>
          </label>
          <button class="btn btn-primary" :disabled="store.busy||!recruitId" @click="assign">派遣驻守</button>
        </div>
      </template>
      <template v-else-if="detailTab==='retrial'">
        <div class="retrial-block">
          <div class="section-heading">
            <div><span class="eyebrow">单场论道 · 3v1</span><h3>再访{{ selected.name }}</h3></div>
            <span class="badge badge-gold">{{ cost }} 行动力</span>
          </div>
          <p class="muted">已攻克宗门可反复论道：单场宗主战，胜利领取固定奖励，失败无奖励；不改变攻克状态与驻守编制。</p>
          <p v-if="retrialReason" class="error-box">{{ retrialReason }}</p>
          <button class="btn btn-primary expedition-start" :disabled="store.busy||!!retrialReason" @click="store.startRun(store.party,'expedition',{sect_id:selected.id,is_retrial:true})">发起论道 · {{ cost }} 行动力</button>
          <div class="section-heading party-heading"><h4>随行弟子 · {{ party.length }} / 6</h4><button class="btn btn-small" @click="$emit('edit')">调整随行队伍</button></div>
          <PartyStrip compact reorder @edit="$emit('edit')" />
          <PartyHealing :party="store.party" />
          <div class="first-loot">
            <strong>论道所得</strong>
            <span v-for="(amount,id) in retrialReward" :key="id">{{ resourceName(id,store.catalog) }} +{{ number(amount,1) }}</span>
            <span v-if="!Object.keys(retrialReward).length">正在读取此宗门所在地区的奖励预览</span>
          </div>
          <details class="sect-rules"><summary>查看宗主情报</summary><div class="leader-intel">
            <span>宗主决战 · 3v1</span>
            <div>
              <span>
                <img :src="characterImage(selected.leader.asset_id)" alt="" class="pixel-art" loading="lazy" />
                {{ selected.leader.name }}
              </span>
            </div>
            <small>{{ selected.leader.active.name }} · {{ selected.leader.active.description }}</small>
          </div></details>
        </div>
      </template>
      <template v-else-if="detailTab==='prepare'">
        <p v-if="reason" class="error-box">{{ reason }}</p>
        <button class="btn btn-primary expedition-start" :disabled="store.busy||!!reason" @click="store.startRun(store.party,'expedition',{sect_id:selected.id})">向 {{ selected.name }} 发起征讨 · {{ cost }} 行动力</button>
        <div class="section-heading">
          <h3>
            随行弟子
            <small>{{ party.length }} / 6</small>
          </h3>
          <button class="btn btn-small" @click="$emit('edit')">调整随行队伍</button>
        </div>
        <PartyStrip compact reorder @edit="$emit('edit')" />
        <PartyHealing :party="store.party" />
        <div class="first-loot"><strong>攻克所得</strong><span v-for="(amount,id) in selected.loot" :key="id">{{ resourceName(id,store.catalog) }} +{{ number(amount,1) }}</span></div>
        <details class="sect-rules"><summary>征讨规则与回岗说明</summary>
        <p class="muted">每轮选三人，残血延续，倒下者本次停战。获胜且存活三／二／一人，分别削减 50／30／15 守备；三轮内破防，才可挑战宗主。</p>
        <p class="muted">值守与驻守弟子出发自动离岗，结算自动回岗。出发消耗 {{ cost }} 行动力，失败不退还；战役可关闭页面后继续。</p>
        </details>
      </template>
      <div v-else class="enemy-intel">
        <div v-for="(team,index) in selected.arena_teams" :key="index"><span>第 {{ index+1 }} 轮擂台 · 3v3</span><div><span v-for="enemy in team" :key="enemy.id" :title="enemy.active.name+'：'+enemy.active.description"><img :src="characterImage(enemy.asset_id)" alt="" class="pixel-art" loading="lazy" />{{ enemy.name }}</span></div></div>
        <div class="leader-intel"><span>宗主决战 · 3v1</span><div><span><img :src="characterImage(selected.leader.asset_id)" alt="" class="pixel-art" loading="lazy" />{{ selected.leader.name }}</span></div><small>{{ selected.leader.active.name }} · {{ selected.leader.active.description }}</small></div>
      </div>
    </article>
    <p v-else-if="focused" class="notice-box">未找到当前地区的这座宗门，请返回地图重新选择。</p>
  </div>
</template>

<style scoped>
.expedition-panel{min-width:0}.sect-map{max-height:min(48dvh,430px);overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.sect-map:focus-visible{outline:2px solid var(--jade);outline-offset:2px}.sect-dossier.focused{padding:0;border:0;background:transparent;box-shadow:none}.back-to-sects{margin-bottom:16px}.sect-detail-tabs{position:sticky;top:0;z-index:1;display:flex;gap:6px;overflow-x:auto;margin:12px 0 18px;padding:8px 0;background:var(--surface);border-bottom:1px solid var(--border)}.sect-detail-tabs>button{flex:1;min-height:44px;padding:8px 12px;white-space:nowrap;background:transparent;border:1px solid transparent;color:var(--muted);font-size:12px}.sect-detail-tabs>button.active{background:var(--jade-light);border-color:#a9b49c;color:var(--jade)}.party-heading{margin-top:20px}.sect-rules{margin-top:18px;border-top:1px solid #d1c3a1}.sect-rules>summary{min-height:44px;padding:12px 0;cursor:pointer;color:var(--jade);font-size:12px}.sect-rules>summary:focus-visible{outline:2px solid var(--jade);outline-offset:2px}.sect-rules .leader-intel img{width:44px;height:48px;object-fit:contain}.sect-rules .leader-intel>div>span{display:flex;align-items:center;gap:10px}.sect-rules .leader-intel small{display:block;margin-top:8px;color:var(--muted);font-size:11px}.sect-rules p{font-size:11px;line-height:1.8}.sect-dossier .retrial-block{margin-top:0;padding-top:0;border-top:0}
.charter-heading{display:flex;gap:20px;justify-content:space-between;align-items:center}.charter-heading h3{font-size:25px;margin:7px 0}.charter-heading p{max-width:650px;margin:0;font-size:12px;line-height:1.8}.charter-seal{flex-shrink:0;font:38px 'SimSun',serif;color:#966a3d;border:1px solid #ab885a;padding:6px 10px;box-shadow:inset 0 0 0 3px var(--surface),inset 0 0 0 4px #b39970}.territory-overview{display:flex;gap:25px;padding:18px 0;border-bottom:1px solid #ccbea0;font-size:11px;color:var(--muted)}.territory-overview strong{font:22px 'SimSun',serif;color:var(--jade);margin:0 4px}.tabs{margin-top:16px}.sect-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0 22px;padding:15px;background:repeating-linear-gradient(0deg,#dae0ca 0 29px,#d4dbc5 29px 30px);border:1px solid #b9c2a3}.sect-marker{position:relative;text-align:left;display:flex;flex-direction:column;gap:7px;min-width:0;padding:19px 12px 12px;background:#f6f1df;border:1px solid #b4aa86;border-top:3px solid #8c6844;box-shadow:2px 3px 0 #5e745526}.sect-marker.selected{border-color:var(--jade);box-shadow:inset 0 0 0 1px var(--jade),3px 3px 0 #67765233}.sect-marker.conquered{background:#dfe8cf;border-top-color:#326c55}.sect-marker>strong{font:20px 'SimSun',serif;color:var(--jade)}.sect-marker>small{font-size:10px;color:var(--muted)}.marker-level{position:absolute;right:9px;top:6px;font-size:9px;color:var(--gold)}.resource-line{font-size:10px;line-height:1.6;color:var(--muted)}.marker-status{font-size:10px;border-top:1px solid #c9c5a6;padding-top:8px;margin-top:auto;color:#326c55;display:flex;align-items:center;gap:6px}.sect-dossier{padding:20px;border:1px solid #b8a985;border-top:3px solid #8c6844;background:#f6f1df;box-shadow:inset 3px 0 #8c68441a}.sect-dossier .section-heading h3{margin:5px 0;font-size:23px}.enemy-intel{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0}.enemy-intel>div{padding:12px;background:#eae5d1;border-left:2px solid #b4a478}.enemy-intel>div>span{font-size:10px;color:var(--gold)}.enemy-intel>div>div{display:flex;flex-wrap:wrap;gap:9px;margin-top:7px}.enemy-intel>div>div>span{display:flex;flex-direction:column;gap:3px;align-items:center;font-size:9px;max-width:80px;text-align:center}.enemy-intel img{height:48px;width:44px;object-fit:contain}.enemy-intel small{display:block;font-size:10px;color:var(--muted);margin-top:8px;line-height:1.6}.first-loot{display:flex;flex-wrap:wrap;gap:9px 14px;padding:14px 0;margin-bottom:20px;border-block:1px solid #d1c3a1;font-size:11px;color:var(--jade)}.first-loot strong{width:100%;color:var(--ink);font-size:13px}.sect-dossier>.muted{font-size:11px;line-height:1.8}.expedition-start{width:100%;min-height:47px;margin-top:10px;box-shadow:inset 0 -3px #213f3655,0 2px 0 #8c684433}.garrison-production{display:flex;flex-wrap:wrap;gap:12px 20px;margin:14px 0;padding:13px 15px;background:#dfe8cf;border:1px solid #b4c39f;border-left:3px solid #326c55;font-size:12px}.garrison-production strong{color:var(--jade);font-weight:500}.garrison-list>div{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #d0c7a9}.garrison-list img{width:44px;height:52px;object-fit:contain;object-position:center bottom;background:#dfe8cf;border:1px solid #adb993}.garrison-list span{flex:1}.garrison-list strong,.garrison-list small{display:block}.garrison-list strong{font:16px 'SimSun',serif}.garrison-list small{font-size:10px;color:var(--muted);margin-top:5px}.garrison-form{display:flex;align-items:flex-end;gap:12px;margin-top:18px}.retrial-block{margin-top:22px;border-top:1px solid #d1c3a1;padding-top:18px}.retrial-block .section-heading h3{font-size:20px}.retrial-block>.muted{font-size:11px;line-height:1.8}.retrial-block .leader-intel{margin:14px 0}.garrison-form label{flex:1;min-width:0;font-size:11px;color:var(--muted)}.garrison-form select{display:block;width:100%;margin-top:6px}@media(max-width:640px){.charter-heading h3{font-size:21px}.charter-seal{font-size:30px}.territory-overview{gap:13px;flex-wrap:wrap}.sect-map{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:8px}.sect-marker{padding:18px 9px 10px}.sect-marker>strong{font-size:17px}.sect-dossier{padding:15px}.enemy-intel{grid-template-columns:1fr}.garrison-form{flex-direction:column;align-items:stretch}.sect-dossier .section-heading{align-items:flex-start;gap:10px}.sect-dossier .section-heading h3{font-size:20px}.sect-dossier .section-heading .btn{font-size:10px}}

.charter-heading{padding-left:13px;border-left:3px solid #326c55}.charter-heading h3{color:#213f36}.charter-seal{color:#8c6844;border-color:#8c6844}.territory-overview{padding:14px 0;border-bottom-style:double;border-color:#bcae89}.sect-marker::after{content:'';position:absolute;top:12px;left:12px;width:16px;height:2px;background:#8c684466}.marker-status::before{content:'';width:6px;height:6px;border:1px solid #98a67d;flex:none}.sect-marker.conquered .marker-status::before{background:#326c55;border-color:#326c55}.sect-marker:focus-visible{outline:2px solid #b38a46;outline-offset:3px}.sect-detail-tabs>button.active{background:#326c55;border-color:#213f36;color:#f6f1df;box-shadow:inset 0 -2px #b38a46}.enemy-intel>div{border:1px solid #c9bd9d;border-left:3px solid #a28c59;background:#eee8d2}.enemy-intel img{background:#dfe8cf;border-bottom:1px solid #9bae89}.first-loot{background:#eee9d5;padding:12px 14px;border-block-color:#bfb28a;margin-bottom:16px}.garrison-list>div>span{min-width:0}.garrison-list strong{color:#213f36}.garrison-list small{line-height:1.6}.garrison-production>span{display:flex;align-items:center;gap:7px}.garrison-production strong{font-variant-numeric:tabular-nums;white-space:nowrap}.garrison-form select{min-height:44px}.sect-detail-tabs>button:focus-visible{outline:2px solid #b38a46;outline-offset:2px}
@media(max-width:640px){.charter-heading{gap:12px;padding-left:10px}.territory-overview{gap:10px;font-size:11px}.garrison-list small{font-size:11px}.garrison-production{gap:10px;font-size:12px}.enemy-intel small,.sect-rules p{font-size:12px}.sect-detail-tabs>button{padding-inline:8px}.sect-marker>strong{overflow-wrap:anywhere}.marker-status{font-size:10px}}

</style>
