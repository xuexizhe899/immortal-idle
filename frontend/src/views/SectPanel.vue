<script setup lang="ts">
import { computed,nextTick,ref } from 'vue'
import GameIcon from '../components/ui/GameIcon.vue'
import { statNames,resourceName, type DisplayCatalog } from '../presentation/gameText'
import { durationFromHours,number } from '../shared/format'
import { useGameStore } from '../stores/game'
import SaveSlotsPanel from './SaveSlotsPanel.vue'
import FacilitiesSection from '../components/game/FacilitiesSection.vue'
import MaterialSources from '../components/game/MaterialSources.vue'
const tabs = [
  { id: 'overview', label: '宗门总览' },
  { id: 'facilities', label: '设施升级' },
  { id: 'income', label: '挂机收益' },
  { id: 'review', label: '出征复盘' },
  { id: 'sources', label: '材料来源' },
  { id: 'saves', label: '存档管理' },
] as const
type SectTab = typeof tabs[number]['id']
const store=useGameStore();const tab=ref<SectTab>('overview')
const panel=ref<HTMLElement|null>(null)
const emit=defineEmits<{open:[panel:string]}>()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const idleRecord=computed(()=>store.state?.idle_record)
const recordStartedAt=computed(()=>idleRecord.value?.started_at ? new Date(idleRecord.value.started_at).toLocaleString('zh-CN') : '')
const settleGains=computed(()=>idleRecord.value ? {cultivation:idleRecord.value.cultivation,spirit_stone:idleRecord.value.spirit_stone,stamina:idleRecord.value.stamina,...idleRecord.value.materials} : {})
const latestGains=computed(()=>store.lastSettle ? {cultivation:store.lastSettle.gained.cultivation,spirit_stone:store.lastSettle.gained.spirit_stone,stamina:store.lastSettle.gained.stamina,...store.lastSettle.gained.materials} : {})
const chronicles=computed(()=>[
  `问道塔已至 ${store.state?.tower_floor??0} 层，新的修行之路仍在前方。`,
  `门下共有 ${store.disciples.length} 位弟子，${store.state?.duty_slots?.length??0} 位正在值守。`,
  store.disciples.some(d=>d.injury_stacks) ? `${store.disciples.filter(d=>d.injury_stacks).length} 位弟子有伤在身，可前往炼丹房疗伤。` : '门下弟子状态良好，随时可整装出发。',
])
const review=computed(()=>store.state?.last_run_review)
const reviewModeName=computed(()=>{
  if(review.value?.sect_id)return `${review.value.is_retrial?'论道':'征讨'} · ${review.value.sect_name??'外宗'}`
  const name=review.value?.world_node_name||(review.value?.mode==='expedition'?'远行':review.value?.mode==='dungeon'?'秘境历练':review.value?.mode==='world'?'守关与迎击':`问道塔 · ${review.value?.tower_tier??1} 阶`)
  return review.value?.world_node_id?`第 ${review.value.region_id} 地区 · ${name}`:name
})
const reviewUnit=computed(()=>review.value?.sect_id?'场':review.value?.mode==='expedition'?'段':review.value?.mode==='dungeon'||review.value?.mode==='world'?'关':'层')
const reviewEndText=computed(()=>({guard_unbroken:'守备未破',insufficient_fighters:'可战弟子不足',round_limit:'回合耗尽',retreated:'主动撤退'} as Record<string,string>)[review.value?.end_reason ?? ''] ?? '战斗失利')
const injuredCount=computed(()=>store.disciples.filter(d=>d.injury_stacks>0).length)
const reviewAdvice=computed(()=>{
  if (!review.value) return ''
  if (injuredCount.value) return `当前有 ${injuredCount.value} 位弟子带伤，可先查看疗伤丹药，再决定下次阵容。`
  if (review.value.end_reason==='round_limit') return '末战二十轮内未能击败敌人。可查看输出与破防配合，下次比较轮数和存活人数。'
  if (!review.value.victory) return '可结合本场先倒下的弟子和敌人招式，检查队伍顺序与培养；下次比较倒下顺序和承伤。'
  return '此行已完成。可用战利品查看培养或专武，下一次比较同类遭遇的轮数与存活人数。'
})
function selectTab(id: SectTab) {
  tab.value = id
  nextTick(() => {
    panel.value?.closest<HTMLElement>('.modal-body')?.scrollTo({ top: 0, behavior: 'auto' })
    const active = panel.value?.querySelector<HTMLButtonElement>(`#sect-tab-${id}`)
    active?.focus({ preventScroll: true })
    active?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' })
  })
}
function onTabKey(event: KeyboardEvent, id: SectTab) {
  const index = tabs.findIndex(item => item.id === id)
  const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length
    : event.key === 'ArrowLeft' ? (index - 1 + tabs.length) % tabs.length
    : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1
  if (next < 0) return
  event.preventDefault()
  selectTab(tabs[next]!.id)
}
</script>
<template>
  <div ref="panel" class="sect-panel">
    <nav class="sect-navigation" role="tablist" aria-label="宗门事务">
      <button v-for="item in tabs" :id="`sect-tab-${item.id}`" :key="item.id" type="button" role="tab" :class="{active:tab===item.id}" :aria-selected="tab===item.id" :aria-controls="`sect-content-${item.id}`" :tabindex="tab===item.id?0:-1" @click="selectTab(item.id)" @keydown="onTabKey($event,item.id)">{{ item.label }}</button>
    </nav>
    <section :id="`sect-content-${tab}`" role="tabpanel" :aria-labelledby="`sect-tab-${tab}`">
      <template v-if="tab==='overview'">
        <div class="sect-intro"><span class="sect-seal">仙</span><div><span class="eyebrow">云岫仙宗</span><h3>兴修山门，育养同道。</h3><p class="muted">门下 {{ store.disciples.length }} 位弟子 · 值守 {{ store.state?.duty_slots?.length??0 }} / 6 · 问道塔 {{ store.state?.tower_floor??0 }} 层</p></div></div>
        <div class="stat-grid"><div v-for="key in ['cultivation','spirit_stone','stamina','reputation'] as const" :key="key" class="stat-cell"><span>{{ statNames[key] }}</span><strong>{{ number(store.resources?.[key],1) }}</strong></div></div>
        <div class="overview-links" aria-label="常用事务">
          <button class="btn btn-primary btn-small" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" />同步挂机收益</button>
          <button class="btn btn-small" @click="selectTab('facilities')">设施升级</button><button class="btn btn-small" @click="selectTab('income')">挂机收益</button><button class="btn btn-small" @click="selectTab('review')">出征复盘</button>
          <button class="btn btn-small btn-quiet" @click="emit('open','codex')">弟子培养</button><button class="btn btn-small btn-quiet" @click="emit('open','duty')">安排值守</button><button class="btn btn-small btn-quiet" @click="emit('open','expedition')">前往山河</button>
        </div>
        <div class="sect-log"><div class="section-heading"><h3>宗门现况</h3><span class="muted">当前修行进度</span></div><p v-for="(log,i) in chronicles" :key="i">{{ log }}</p><details v-if="store.state?.logs?.length"><summary>最近宗门纪事</summary><p v-for="(log,index) in store.state.logs.slice(-5)" :key="index">{{ log }}</p></details><p v-else class="muted">新宗初立，来日方长。</p></div>
      </template>
      <FacilitiesSection v-else-if="tab==='facilities'" @open="emit('open',$event)" />
      <template v-else-if="tab==='income'">
        <div class="idle-section"><div><h3>同步挂机收益</h3><p class="muted">后台按服务器时间自动记账，单次离线最多补算 12 小时；累计记录不因在线操作或同步清零。</p></div><button class="btn btn-primary" :disabled="store.busy" @click="store.settle()"><GameIcon name="leaf" />同步挂机收益</button></div>
        <div v-if="idleRecord" class="settle-result notice-box"><span class="eyebrow">累计挂机收益 · 已自动入账</span><p>累计有效时长 {{ durationFromHours(idleRecord.elapsed_hours) }}</p><div class="chips"><span v-for="(n,key) in settleGains" :key="key" class="badge">{{ resourceName(key,catalog) }} +{{ number(n,2) }}</span></div><p class="muted">{{ recordStartedAt ? `记录起点：${recordStartedAt}；` : '' }}从记录建立起累计，旧历史不追溯统计，以上收益无需再次领取。</p><p v-if="idleRecord.dropped_hours>0" class="muted">累计有 {{ durationFromHours(idleRecord.dropped_hours) }} 超出单次 12 小时上限，未计入收益。</p></div>
        <p v-else class="muted">后台会从首次有效结算起保存累计记录，旧历史不追溯统计。</p>
        <details v-if="store.lastSettle"><summary>本次同步新增 · {{ durationFromHours(store.lastSettle.elapsed_hours) }}</summary><p class="muted">以下新增已自动入账，累计记录包含这些收益。</p><div class="chips"><span v-for="(n,key) in latestGains" :key="key" class="badge">{{ resourceName(key,catalog) }} +{{ number(n,2) }}</span></div></details>
      </template>
      <template v-else-if="tab==='review'">
        <div v-if="store.lastRun && !review" class="run-result notice-box"><span class="eyebrow">最近出征</span><h3>{{ store.lastRun.victory ? '问道功成' : '整顿再来' }}</h3><p>到达 {{ store.lastRun.cleared }} 层 · 战利品已入库</p><div class="chips"><span v-for="(value,key) in store.lastRun.loot" :key="key" class="badge">{{ resourceName(key,catalog) }} +{{ number(value,1) }}</span></div></div>
        <section v-if="review" class="run-review notice-box">
  <span class="eyebrow">上次出征复盘</span><span v-if="review.practice" class="badge badge-muted">演练 · 无正式奖励</span>
  <h3>{{ reviewModeName }} · {{ review.victory ? '已完成' : '暂告失败' }}</h3>
  <p>{{ review.sect_id ? '完成交锋' : '到达' }} {{ review.cleared }} / {{ review.total_nodes }} {{ reviewUnit }} · {{ review.practice ? '演练无正式奖励'+(review.victory?'':' · '+reviewEndText) : review.victory ? '战利品已结算' : reviewEndText }}</p>
  <template v-if="review.last_battle">
    <p>末战 {{ review.last_battle.rounds }} 轮 · 我方承伤 {{ review.last_battle.damage }} · 气血 {{ review.last_battle.hp_before }} → {{ review.last_battle.hp_after }}</p>
    <p v-if="review.last_battle.first_down_name">本场先倒下：{{ review.last_battle.first_down_name }}</p>
    <p>我方实际治疗 {{ review.last_battle.healed }} · 施加护盾 {{ review.last_battle.shield_applied ?? '未记录' }} · 护盾吸收 {{ review.last_battle.shield_absorbed ?? '未记录' }}</p>
    <p v-if="review.last_battle.surviving_enemies.length">战后仍存活的敌人：{{ review.last_battle.surviving_enemies.map(enemy => enemy.name).join('、') }}</p>
    <details v-if="review.last_battle.key_actions.length">
      <summary>查看三条最高伤害记录</summary>
      <p v-for="(action,index) in review.last_battle.key_actions" :key="index">第 {{ action.round }} 轮 · 行动 {{ action.sequence }}：{{ action.actor_name }}的{{ action.skill_name }}对{{ action.target_name }}造成 {{ action.amount }} 伤害</p>
    </details>
  </template>
  <p v-else class="muted">本次未记录末战详情。</p>
  <div class="chips"><span v-for="(value,key) in review.loot" :key="key" class="badge">{{ resourceName(key,catalog) }} +{{ number(value,1) }}</span></div>
  <p class="review-advice">下次可尝试：{{ review.practice?'调整阵容与装备后再次演练，比较交锋轮数与存活人数。':reviewAdvice }}</p>
  <p v-if="store.state?.active_run" class="muted">当前出征尚未结算，可先查阅；结束后再调整阵容和培养。</p>
  <div class="review-actions">
    <button class="btn btn-small" @click="emit('open','codex')">查看阵容与培养</button>
    <button class="btn btn-small" @click="emit('open',injuredCount ? 'alchemy' : 'forge')">{{ injuredCount ? '查看疗伤丹药' : '查看专属武器' }}</button>
  </div>
        </section>
        <p v-else-if="!store.lastRun" class="notice-box">尚无出征复盘。完成并结算一次出征后，可在这里查看战果与下次培养方向。</p>
      </template>
      <MaterialSources v-else-if="tab==='sources'" @open="emit('open',$event)" />
      <SaveSlotsPanel v-else-if="tab==='saves'" />
    </section>
  </div>
</template>
<style scoped>
.sect-panel{min-width:0}.sect-navigation{position:sticky;top:0;z-index:2;display:flex;gap:4px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin;scroll-padding-inline:14px;margin:-24px -26px 22px;padding:10px 26px;background:var(--surface);border-bottom:1px solid var(--border)}.sect-navigation>button{flex:none;min-height:44px;padding:8px 12px;white-space:nowrap;border:1px solid transparent;background:transparent;color:var(--muted);font-size:13px}.sect-navigation>button.active{border-color:#a9b49c;background:var(--jade-light);color:var(--jade)}.sect-navigation>button:focus-visible,.sect-log summary:focus-visible{outline:2px solid var(--jade);outline-offset:2px}.overview-links{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.sect-log>details{margin-top:10px}.sect-log summary{padding:8px 0;cursor:pointer;color:var(--jade);font-size:12px}.sect-log details>p{font-size:11px;color:var(--muted);margin:6px 0}
.run-result{margin-top:18px}.run-result h3{margin:6px 0}.run-result p{margin-bottom:10px}.run-review{margin-top:18px}.run-review h3{margin:6px 0}.run-review p{margin:6px 0}.review-advice{color:var(--jade)}.review-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.run-review p{overflow-wrap:anywhere}.run-review summary{cursor:pointer;padding:8px 0}.run-review summary:focus-visible{outline:2px solid var(--jade);outline-offset:2px}
.sect-intro{display:flex;align-items:center;gap:22px;margin:12px 0 28px}.sect-seal{width:72px;height:82px;display:grid;place-items:center;border:1px solid #a59f7c;box-shadow:inset 0 0 0 5px var(--surface),inset 0 0 0 6px #a59f7c;color:var(--jade);font:43px 'SimSun',serif}.sect-intro h3{font-size:23px;margin:6px 0}.sect-intro p{margin:0}.idle-section{display:flex;justify-content:space-between;gap:20px;align-items:center;margin:26px 0 18px;padding:22px 0;border-block:1px solid #d5c9ad}.idle-section h3{margin:0 0 7px}.idle-section p{margin:0}.settle-result>.eyebrow{font-size:8px}.settle-result p{margin:5px 0 10px}.settle-result .muted{margin:12px 0 0}.sect-log{margin-top:28px}.sect-log>p{font-size:11px;padding:8px 0;border-bottom:1px solid #ded5bf;margin:0;color:var(--muted)}
@media(max-width:640px){.sect-navigation{margin:-18px -14px 18px;padding:9px 14px;gap:3px}.sect-navigation>button{font-size:12px;padding-inline:10px}.sect-intro{gap:14px;margin-bottom:20px}.sect-seal{width:52px;height:65px;flex:none;font-size:32px}.sect-intro h3{font-size:18px}.sect-intro .eyebrow{font-size:8px}.idle-section{flex-direction:column;align-items:flex-start;gap:14px}.idle-section>.btn{width:100%}.overview-links>.btn{min-height:40px;flex:1 0 calc(33.333% - 8px);padding-inline:8px;font-size:11px}}
</style>
