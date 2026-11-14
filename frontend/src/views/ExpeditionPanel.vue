<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PartyStrip from '../components/game/PartyStrip.vue'
import PartyHealing from '../components/game/PartyHealing.vue'
import { characterImage, discipleImage } from '../presentation/assetPaths'
import { resourceName } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

defineEmits<{ edit: [] }>()
const store = useGameStore()
const selectedId = computed({
  get: () => store.targetSectId,
  set: (id: string) => { store.targetSectId = id },
})
const recruitId = ref('')
const filter = ref('all')
const sects = computed(() => store.state?.sects ?? [])
const visible = computed(() => sects.value.filter(sect =>
  filter.value === 'all' || (filter.value === 'conquered' ? sect.conquered : !sect.conquered),
))
const selected = computed(() => sects.value.find(sect => sect.id === selectedId.value))
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
const reason = computed(() => {
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
watch(sects, list => {
  if (!list.some(sect => sect.id === selectedId.value)) selectedId.value = list[0]?.id ?? ''
}, { immediate: true })
watch(selectedId, () => { recruitId.value = '' })
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
  <section class="expedition-charter">
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
    <div class="sect-map">
      <button
        v-for="sect in visible"
        :key="sect.id"
        class="sect-marker"
        :class="{selected:sect.id===selectedId,conquered:sect.conquered}"
        :aria-pressed="sect.id===selectedId"
        @click="selectedId=sect.id"
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
    <article v-if="selected" class="sect-dossier">
      <p v-if="resourceGoal" class="notice-box">{{ resourceGoal }}</p>
      <div class="section-heading">
        <div>
          <span class="eyebrow">{{ selected.conquered ? '驻守经营' : '战前情报' }}</span>
          <h3>{{ selected.name }}</h3>
        </div>
        <span class="badge badge-gold">{{ selected.style }} · {{ selected.level }} 阶</span>
      </div>
      <template v-if="selected.conquered">
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
      <template v-else>
        <div class="enemy-intel">
          <div v-for="(team,index) in selected.arena_teams" :key="index">
            <span>第 {{ index+1 }} 轮擂台 · 3v3</span>
            <div>
              <span
                v-for="enemy in team"
                :key="enemy.id"
                :title="enemy.active.name+'：'+enemy.active.description"
              >
                <img
                  :src="characterImage(enemy.asset_id)"
                  alt=""
                  class="pixel-art"
                  loading="lazy"
                />
                {{ enemy.name }}
              </span>
            </div>
          </div>
          <div class="leader-intel">
            <span>宗主决战 · 3v1</span>
            <div>
              <span>
                <img
                  :src="characterImage(selected.leader.asset_id)"
                  alt=""
                  class="pixel-art"
                  loading="lazy"
                />
                {{ selected.leader.name }}
              </span>
            </div>
            <small>{{ selected.leader.active.name }} · {{ selected.leader.active.description }}</small>
          </div>
        </div>
        <div class="first-loot">
          <strong>攻克所得</strong>
          <span v-for="(amount,id) in selected.loot" :key="id">{{ resourceName(id,store.catalog) }} +{{ number(amount,1) }}</span>
        </div>
        <div class="section-heading">
          <h3>
            随行弟子
            <small>{{ party.length }} / 6</small>
          </h3>
          <button class="btn btn-small" @click="$emit('edit')">调整随行队伍</button>
        </div>
        <PartyStrip compact reorder @edit="$emit('edit')" />
        <PartyHealing :party="store.party" />
        <p class="muted">每轮选三人，残血延续，倒下者本次停战。获胜且存活三／二／一人，分别削减 50／30／15 守备；三轮内破防，才可挑战宗主。</p>
        <p class="muted">值守与驻守弟子出发自动离岗，结算自动回岗。出发消耗 {{ cost }} 行动力，失败不退还；战役可关闭页面后继续。</p>
        <p v-if="reason" class="error-box">{{ reason }}</p>
        <button
          class="btn btn-primary expedition-start"
          :disabled="store.busy||!!reason"
          @click="store.startRun(store.party,'expedition',{sect_id:selected.id})"
        >
          向
          {{ selected.name }}
          发起征讨 ·
          {{ cost }}
          行动力
        </button>
      </template>
    </article>
  </section>
</template>

<style scoped>
.charter-heading{display:flex;gap:20px;justify-content:space-between;align-items:center}.charter-heading h3{font-size:25px;margin:7px 0}.charter-heading p{max-width:650px;margin:0;font-size:12px;line-height:1.8}.charter-seal{flex-shrink:0;font:38px 'SimSun',serif;color:#966a3d;border:1px solid #ab885a;padding:6px 10px;box-shadow:inset 0 0 0 3px var(--surface),inset 0 0 0 4px #b39970}.territory-overview{display:flex;gap:25px;padding:18px 0;border-bottom:1px solid #ccbea0;font-size:11px;color:var(--muted)}.territory-overview strong{font:22px 'SimSun',serif;color:var(--jade);margin:0 4px}.tabs{margin-top:16px}.sect-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0 22px;padding:15px;background:repeating-linear-gradient(0deg,#dae0ca 0 29px,#d4dbc5 29px 30px);border:1px solid #b9c2a3}.sect-marker{position:relative;text-align:left;display:flex;flex-direction:column;gap:7px;min-width:0;padding:19px 12px 12px;background:#f3ecd8;border:1px solid #bdb18c;box-shadow:3px 3px 0 #6776521c}.sect-marker.selected{border-color:var(--jade);box-shadow:inset 0 0 0 1px var(--jade),3px 3px 0 #67765233}.sect-marker.conquered{background:#e2e9d4}.sect-marker>strong{font:20px 'SimSun',serif;color:var(--jade)}.sect-marker>small{font-size:10px;color:var(--muted)}.marker-level{position:absolute;right:9px;top:6px;font-size:9px;color:var(--gold)}.resource-line{font-size:10px;line-height:1.6;color:var(--muted)}.marker-status{font-size:10px;border-top:1px solid #d5c8a8;padding-top:8px;margin-top:auto;color:var(--jade)}.sect-dossier{padding:22px;border:1px solid #c3b48e;background:#f6efdd}.sect-dossier .section-heading h3{margin:5px 0;font-size:23px}.enemy-intel{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0}.enemy-intel>div{padding:12px;background:#eae5d1;border-left:2px solid #b4a478}.enemy-intel>div>span{font-size:10px;color:var(--gold)}.enemy-intel>div>div{display:flex;flex-wrap:wrap;gap:9px;margin-top:7px}.enemy-intel>div>div>span{display:flex;flex-direction:column;gap:3px;align-items:center;font-size:9px;max-width:80px;text-align:center}.enemy-intel img{height:48px;width:44px;object-fit:contain}.enemy-intel small{display:block;font-size:10px;color:var(--muted);margin-top:8px;line-height:1.6}.first-loot{display:flex;flex-wrap:wrap;gap:9px 14px;padding:14px 0;margin-bottom:20px;border-block:1px solid #d1c3a1;font-size:11px;color:var(--jade)}.first-loot strong{width:100%;color:var(--ink);font-size:13px}.sect-dossier>.muted{font-size:11px;line-height:1.8}.expedition-start{width:100%;margin-top:10px}.garrison-production{display:flex;flex-wrap:wrap;gap:15px;margin:16px 0;padding:14px;background:#e1e8d2;font-size:12px}.garrison-production strong{color:var(--jade);font-weight:500}.garrison-list>div{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #d8cdae}.garrison-list img{width:40px;height:48px;object-fit:cover;object-position:top}.garrison-list span{flex:1}.garrison-list strong,.garrison-list small{display:block}.garrison-list strong{font:16px 'SimSun',serif}.garrison-list small{font-size:10px;color:var(--muted);margin-top:5px}.garrison-form{display:flex;align-items:flex-end;gap:12px;margin-top:18px}.garrison-form label{flex:1;min-width:0;font-size:11px;color:var(--muted)}.garrison-form select{display:block;width:100%;margin-top:6px}@media(max-width:640px){.charter-heading h3{font-size:21px}.charter-seal{font-size:30px}.territory-overview{gap:13px;flex-wrap:wrap}.sect-map{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:8px}.sect-marker{padding:18px 9px 10px}.sect-marker>strong{font-size:17px}.sect-dossier{padding:15px}.enemy-intel{grid-template-columns:1fr}.garrison-form{flex-direction:column;align-items:stretch}.sect-dossier .section-heading{align-items:flex-start;gap:10px}.sect-dossier .section-heading h3{font-size:20px}.sect-dossier .section-heading .btn{font-size:10px}}
</style>
