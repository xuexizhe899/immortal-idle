import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const source = await readFile(new URL('../src/views/SectPanel.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
const transpile = code => ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const makeSetup = new Function('computed', 'nextTick', 'ref', 'useGameStore', 'defineEmits', 'statNames', 'resourceName', 'number', `${transpile(script)}
  return { tabs, tab, panel, store, emit, catalog, settleGains, chronicles, review, reviewModeName,
    reviewUnit, reviewEndText, injuredCount, reviewAdvice, selectTab, onTabKey, statNames, resourceName, number }`)
const template = source.match(/<template>([\s\S]*?)<\/template>\s*<style scoped>/)[1]
const renderCode = compile(template, { mode: 'function', expressionPlugins: ['typescript'] }).code
const render = new Function('Vue', transpile(renderCode))(Vue)
render._rc = true

function setupView() {
  const events = []
  const store = Vue.reactive({
    busy: false, disciples: [{ injury_stacks: 0 }], resources: { cultivation: 21, spirit_stone: 18, stamina: 3, reputation: 5 },
    state: { tower_floor: 4, duty_slots: [], logs: ['第一条纪事', '第二条纪事', '第三条纪事', '第四条纪事', '第五条纪事', '第六条纪事'], last_run_review: null },
    catalog: null, lastSettle: null, lastRun: null, settle: () => { throw new Error('changing sections must not collect rewards') },
  })
  const view = makeSetup(Vue.computed, Vue.nextTick, Vue.ref, () => store, () => (...args) => events.push(args),
    { cultivation: '修为', spirit_stone: '灵石', stamina: '行动力', reputation: '声望' }, id => id, value => String(value ?? 0))
  return { ...view, events }
}

async function renderView(view) {
  const mounted = []
  const childEvents = {}
  const components = Object.fromEntries(['FacilitiesSection', 'MaterialSources', 'SaveSlotsPanel'].map(name => [name, Vue.defineComponent({
    name, emits: ['open'], setup(_props, { emit }) {
      mounted.push(name)
      childEvents[name] = panel => emit('open', panel)
      return () => Vue.h('div', { 'data-child': name }, name)
    },
  })]))
  components.GameIcon = { render: () => Vue.h('i') }
  // Render the real template with the real setup state; child modules retain their own existing tests.
  const html = await renderToString(Vue.createSSRApp({ components, setup: () => view, render }))
  return { html, mounted, childEvents }
}

test('overview stays compact while the six sections remain reachable', async () => {
  const view = setupView()
  const { html, mounted } = await renderView(view)
  assert.equal((html.match(/role="tab"/g) ?? []).length, 6)
  assert.match(html, /id="sect-content-overview" role="tabpanel"/)
  assert.match(html, /兴修山门，育养同道/)
  assert.match(html, /宗门现况/)
  assert.match(html, /<details><summary>最近宗门纪事/)
  assert.doesNotMatch(html, /第一条纪事/)
  assert.match(html, /第六条纪事/)
  assert.doesNotMatch(html, /收取挂机收益|上次出征复盘|尚无出征复盘/)
  assert.deepEqual(mounted, [])
  view.store.busy = true
  assert.match((await renderView(view)).html, /<button class="btn btn-primary btn-small" disabled><i\b[^>]*><\/i>收取收益<\/button>/)
})

test('facilities, sources and saves mount separately and preserve parent navigation events', async () => {
  const view = setupView()
  for (const [tab, name] of [['facilities', 'FacilitiesSection'], ['sources', 'MaterialSources'], ['saves', 'SaveSlotsPanel']]) {
    view.selectTab(tab)
    await Vue.nextTick()
    const { html, mounted, childEvents } = await renderView(view)
    assert.deepEqual(mounted, [name])
    assert.match(html, new RegExp(`id="sect-content-${tab}" role="tabpanel"`))
    assert.doesNotMatch(html, /兴修山门，育养同道|收取挂机收益|上次出征复盘/)
    if (tab !== 'saves') childEvents[name]('expedition')
  }
  assert.deepEqual(view.events, [['open', 'expedition'], ['open', 'expedition']])
})

test('income retains settled gains, the offline cap message and the busy collection lock', async () => {
  const view = setupView()
  view.store.lastSettle = { elapsed_hours: 12, dropped_hours: 3, gained: { cultivation: 8, spirit_stone: 6, stamina: 2, materials: { chi_tong: 4 } } }
  view.selectTab('income')
  await Vue.nextTick()
  let output = await renderView(view)
  assert.match(output.html, /收取挂机收益/)
  assert.match(output.html, /超出 12 小时的 3 小时不计入收益/)
  assert.match(output.html, /chi_tong \+4/)
  assert.doesNotMatch(output.html, /兴修山门，育养同道|宗门现况/)
  assert.deepEqual(output.mounted, [])
  view.store.busy = true
  output = await renderView(view)
  assert.match(output.html, /<button class="btn btn-primary" disabled><i\b[^>]*><\/i>收取收益<\/button>/)
})

test('review preserves recorded details, the old-result fallback and the empty state', async () => {
  const view = setupView()
  view.selectTab('review')
  await Vue.nextTick()
  assert.match((await renderView(view)).html, /尚无出征复盘/)
  view.store.lastRun = { victory: true, cleared: 5, loot: { spirit_stone: 7 } }
  assert.match((await renderView(view)).html, /问道功成.*到达 5 层/s)
  view.store.state.last_run_review = {
    mode: 'world', world_node_id: 'r2:gate:1', world_node_name: '山门守关', region_id: 2,
    practice: true, victory: false, cleared: 0, total_nodes: 1, end_reason: 'round_limit', loot: {},
    last_battle: { rounds: 20, damage: 120, hp_before: 180, hp_after: 0, healed: 25,
      shield_applied: 30, shield_absorbed: 28, first_down_name: '甲弟子', surviving_enemies: [{ name: '镇关灵兽' }],
      key_actions: [{ round: 2, sequence: 7, actor_name: '乙弟子', skill_name: '破阵', target_name: '镇关灵兽', amount: 36 }] },
  }
  const { html } = await renderView(view)
  assert.match(html, /第 2 地区 · 山门守关/)
  assert.match(html, /演练 · 无正式奖励/)
  assert.match(html, /本场先倒下：甲弟子/)
  assert.match(html, /施加护盾 30 · 护盾吸收 28/)
  assert.match(html, /第 2 轮 · 行动 7：乙弟子的破阵对镇关灵兽造成 36 伤害/)
  assert.doesNotMatch(html, /问道功成|收取挂机收益/)
})

test('section selection resets only the owning scroll area and keeps its active tab reachable', async () => {
  const view = setupView()
  const actions = []
  view.panel.value = Vue.markRaw({
    closest: selector => { assert.equal(selector, '.modal-body'); return { scrollTo: options => actions.push(['scroll', options]) } },
    querySelector: selector => ({ focus: options => actions.push(['focus', selector, options]), scrollIntoView: options => actions.push(['reveal', selector, options]) }),
  })
  view.selectTab('saves')
  await Vue.nextTick()
  assert.equal(view.tab.value, 'saves')
  assert.deepEqual(actions, [
    ['scroll', { top: 0, behavior: 'auto' }],
    ['focus', '#sect-tab-saves', { preventScroll: true }],
    ['reveal', '#sect-tab-saves', { block: 'nearest', inline: 'nearest', behavior: 'auto' }],
  ])
  function key(key, id) {
    const event = { key, defaultPrevented: false, preventDefault() { this.defaultPrevented = true } }
    view.onTabKey(event, id)
    return event
  }
  assert.equal(key('ArrowRight', 'saves').defaultPrevented, true)
  assert.equal(view.tab.value, 'overview')
  key('ArrowLeft', 'overview')
  assert.equal(view.tab.value, 'saves')
  key('Home', 'saves')
  assert.equal(view.tab.value, 'overview')
  key('End', 'overview')
  assert.equal(view.tab.value, 'saves')
  assert.equal(key('Enter', 'saves').defaultPrevented, false)
  await Vue.nextTick()
})
