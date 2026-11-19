import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const transpile = code => ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const displaySource = (await readFile(new URL('../src/presentation/gameText.ts', import.meta.url), 'utf8'))
  .replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '')
const number = value => String(value ?? 0)
const display = new Function('number', `${transpile(displaySource)}\nreturn { leanNames, leanDescriptions, resourceName, statNames, matchesProductionTarget, resourceDutyLeans }`)(number)
const modules = new Map()
for (const name of ['DutyPanel', 'ExpeditionPanel']) {
  const source = await readFile(new URL(`../src/views/${name}.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = descriptor.scriptSetup.content.replace(/^import .*\r?\n/gm, '')
  const syntax = ts.createSourceFile(`${name}.ts`, script, ts.ScriptTarget.ES2022, true)
  const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
    ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
    : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
  const code = compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true, expressionPlugins: ['typescript'] }).code
  modules.set(name, { script, names, render: new Function('Vue', transpile(code))(Vue) })
}

function enemy(id) {
  return { id, name: `守关${id}`, asset_id: id, active: { name: '破阵剑诀', description: '真实宗主情报' } }
}
function sect(id, region, conquered) {
  return { id, region_id: region, area: 1, name: '同名剑宗', style: '剑修', level: region,
    conquered, material_id: 'chi_tong', special_material_id: 'jade', garrison: [],
    loot: { chi_tong: region * 8 }, arena_teams: [[enemy('一'), enemy('二'), enemy('三')]], leader: enemy('宗主') }
}
function makeStore() {
  const calls = []
  const loads = []
  const sects = [sect('r1:one', 1, true), sect('r1:two', 1, false), sect('r2:one', 2, true)]
  sects[0].garrison = [{ disciple_id: 'd4' }]
  const store = Vue.reactive({
    slotId: 1, revision: 1, busy: false, error: null, targetSectId: '', productionTarget: '',
    disciples: ['甲', '乙', '丙', '丁', '戊', '己', '庚'].map((name, index) => ({ id: `d${index + 1}`, template_id: `t${index + 1}`, busy: index === 2, injury_stacks: index === 3 ? 1 : 0 })),
    party: ['d1', 'd2', 'd4'], resources: { cultivation: 10, spirit_stone: 10, stamina: 8 },
    catalog: { materials: { chi_tong: '赤铜', jade: '灵玉' }, modes: { expedition: { stamina_cost: 2 } },
      disciples: Object.fromEntries(['甲', '乙', '丙', '丁', '戊', '己', '庚'].map((name, index) => [`t${index + 1}`, { name: `${name}弟子`, lean: index === 1 ? 'craft' : 'attack', production_specialty: index === 1 ? 'chi_tong' : 'jade' }])) },
    state: { active_run: null, facility_levels: { training: 1, hall: 1 }, inventory: { chi_tong: 5 }, duty_slots: [{ disciple_id: 'd1' }], sects,
      world: { current_region: 1, unlocked_areas: { 1: 1, 2: 1 } } },
    worldMap: { regions: [1, 2].map(id => ({ id, nodes: sects.filter(item => item.region_id === id).map(item => ({ sect_id: item.id, retrial_rewards: { chi_tong: id === 2 ? 17 : 4 } })) })) },
    production: { cultivation: 1, spirit_stone: 2, stamina: 3, materials: { chi_tong: 4 }, garrisons: { 'r1:one': { chi_tong: 2 }, 'r2:one': { chi_tong: 9 } } },
    assignmentsLoading: false,
    assignments: [{ disciple_id: 'd4', post: 'garrison', sect_id: 'r1:one', duty_rates: { material_rate: .1 }, garrison_rates: { material_chi_tong_flat: 2 } }],
    loadAssignments: async () => { loads.push(true) },
    productionDestination: () => ({ panel: 'duty', label: '安排值守' }),
    assignDuty: async id => { calls.push(['assignDuty', id]) },
    unassignDuty: async id => { calls.push(['unassignDuty', id]) },
    assignGarrison: async (...args) => { calls.push(['assignGarrison', ...args]) },
    unassignGarrison: async (...args) => { calls.push(['unassignGarrison', ...args]) },
    startRun: (...args) => { calls.push(['startRun', ...args]) },
  })
  return { store, calls, loads }
}
function setupView(name, props = {}) {
  const fixture = makeStore()
  const module = modules.get(name)
  const testProps = Vue.reactive({ focused: false, readOnly: false, ...props })
  const events = []
  const bindings = { computed: Vue.computed, nextTick: Vue.nextTick, ref: Vue.ref, watch: Vue.watch,
    ...display, number, useGameStore: () => fixture.store, defineProps: () => testProps,
    defineEmits: () => (...args) => events.push(args), discipleImage: id => `/disciples/${id}.png`, characterImage: id => `/characters/${id}.png` }
  const scope = Vue.effectScope()
  // Exercise the real setup, render functions and handlers without a browser or a copied navigation model.
  const view = scope.run(() => new Function(...Object.keys(bindings), `${transpile(module.script)}\nreturn { ${module.names.join(', ')} }`)(...Object.values(bindings)))
  return { ...fixture, ...view, bindings, testProps, events, render: module.render, stop: () => scope.stop() }
}
function flatten(node) {
  if (Array.isArray(node)) return node.flatMap(flatten)
  return node && typeof node === 'object' ? [node, ...(Array.isArray(node.children) ? flatten(node.children) : [])] : []
}
function textOf(node) {
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (!node || typeof node !== 'object') return String(node ?? '')
  if (node.type === Vue.Comment) return ''
  return typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? textOf(node.children) : ''
}
async function renderView(view) {
  const roots = []
  const components = Object.fromEntries(['PartyStrip', 'PartyHealing'].map(name => [name, { name, render: () => Vue.h('div', { 'data-child': name }) }]))
  const app = Vue.createSSRApp({ components, setup: () => ({ ...view.bindings, ...view, ...view.testProps }), render(...args) {
    const result = view.render.apply(this, args)
    roots.push(result)
    return result
  } })
  return { html: await renderToString(app), nodes: roots.flatMap(flatten) }
}
function button(nodes, label) {
  const result = nodes.find(node => node.type === 'button' && textOf(node).replace(/\s+/g, ' ').includes(label))
  assert.ok(result, `missing button: ${label}`)
  return result
}
function rowButton(nodes, name) {
  const row = nodes.find(node => node.type === 'div' && String(node.props?.class).includes('duty-row') && textOf(node).includes(name))
  assert.ok(row, `missing disciple: ${name}`)
  return flatten(row).find(node => node.type === 'button')
}

test('duty opens directly on assignment and renders posts, production and previews separately', async t => {
  const view = setupView('DutyPanel')
  t.after(view.stop)
  let output = await renderView(view)
  assert.match(output.html, /可安排值守的弟子|安排上岗/)
  assert.doesNotMatch(output.html, /class="duty-slots"|宗门每小时总产出|弟子分配总览/)
  view.selectTab('posts')
  output = await renderView(view)
  assert.match(output.html, /卸下值守|待安排/)
  assert.doesNotMatch(output.html, /class="duty-roster"|宗门每小时总产出|弟子分配总览/)
  output.nodes.find(node => node.type === 'button' && String(node.props?.class).includes('btn') && textOf(node) === '安排弟子').props.onClick()
  assert.equal(view.tab.value, 'roster')
  view.selectTab('production')
  output = await renderView(view)
  assert.match(output.html, /宗门每小时总产出|赤铜/)
  assert.doesNotMatch(output.html, /class="duty-roster"|class="duty-slots"|弟子分配总览/)
  view.selectTab('assignments')
  output = await renderView(view)
  assert.match(output.html, /弟子分配总览|改值守得|失去驻守/)
  assert.doesNotMatch(output.html, /class="duty-roster"|class="duty-slots"|宗门每小时总产出/)
  assert.deepEqual(view.calls, [])
  assert.equal(view.loads.length, 1)
})

test('duty search and specialty ordering retain readonly, busy, occupied and full-roster restrictions', async t => {
  const view = setupView('DutyPanel')
  t.after(view.stop)
  view.store.productionTarget = 'chi_tong'
  assert.equal(view.roster.value[0].id, 'd2')
  view.search.value = '乙'
  assert.deepEqual(view.roster.value.map(item => item.id), ['d2'])
  let output = await renderView(view)
  await rowButton(output.nodes, '乙弟子').props.onClick()
  assert.deepEqual(view.calls, [['assignDuty', 'd2']])
  view.testProps.readOnly = true
  assert.equal(rowButton((await renderView(view)).nodes, '乙弟子').props.disabled, true)
  view.testProps.readOnly = false
  view.search.value = ''
  output = await renderView(view)
  assert.equal(rowButton(output.nodes, '丙弟子').props.disabled, true)
  assert.match(textOf(rowButton(output.nodes, '丁弟子')), /调回值守/)
  await rowButton(output.nodes, '甲弟子').props.onClick()
  assert.deepEqual(view.calls[1], ['unassignDuty', 'd1'])
  view.store.busy = true
  assert.equal(rowButton((await renderView(view)).nodes, '甲弟子').props.disabled, true)
  view.store.busy = false
  view.store.state.duty_slots = view.store.disciples.slice(0, 6).map(item => ({ disciple_id: item.id }))
  output = await renderView(view)
  assert.equal(rowButton(output.nodes, '庚弟子').props.disabled, true)
  assert.equal(rowButton(output.nodes, '甲弟子').props.disabled, false)
  view.search.value = '不存在'
  assert.match((await renderView(view)).html, /暂无匹配弟子/)
})

test('focused expedition keeps exact targets and never substitutes a same-name sect from another region', async t => {
  const view = setupView('ExpeditionPanel', { focused: true })
  t.after(view.stop)
  view.store.targetSectId = 'r1:one'
  await Vue.nextTick()
  assert.equal(view.selected.value.id, 'r1:one')
  assert.doesNotMatch((await renderView(view)).html, /class="sect-map"|择一山门|返回宗门列表/)
  view.store.targetSectId = 'r2:one'
  await Vue.nextTick()
  assert.equal(view.store.targetSectId, 'r2:one')
  assert.equal(view.selected.value, undefined)
  assert.match((await renderView(view)).html, /未找到当前地区的这座宗门/)
  view.store.state.world.current_region = 2
  await Vue.nextTick()
  assert.equal(view.selected.value.id, 'r2:one')
  view.store.targetSectId = 'missing'
  await Vue.nextTick()
  assert.equal(view.store.targetSectId, 'missing')
  assert.equal(view.selected.value, undefined)
})

test('conquered expedition separates garrisons and retrials while preserving exact assignments and server rewards', async t => {
  const view = setupView('ExpeditionPanel', { focused: true })
  t.after(view.stop)
  view.store.state.world.current_region = 2
  view.store.targetSectId = 'r2:one'
  view.store.catalog.disciples.t1.production_specialty = 'wood'
  await Vue.nextTick()
  let output = await renderView(view)
  assert.match(output.html, /派遣驻守/)
  assert.doesNotMatch(output.html, /发起论道 ·|论道所得|data-child="PartyStrip"/)
  assert.ok(!view.candidates.value.some(item => item.id === 'd3'))
  assert.equal(view.candidates.value[0].id, 'd2')
  view.recruitId.value = 'd2'
  output = await renderView(view)
  await button(output.nodes, '派遣驻守').props.onClick()
  assert.deepEqual(view.calls, [['assignGarrison', 'r2:one', 'd2']])
  button(output.nodes, '宗主论道').props.onClick()
  output = await renderView(view)
  assert.doesNotMatch(output.html, /class="garrison-form"|每人独立贡献产出/)
  assert.match(output.html, /赤铜 \+17/)
  assert.ok(output.html.indexOf('发起论道 ·') < output.html.indexOf('data-child="PartyStrip"'))
  assert.match(output.html, /<details class="sect-rules"><summary>查看宗主情报/)
  await button(output.nodes, '发起论道 · 2 行动力').props.onClick()
  assert.deepEqual(view.calls[1], ['startRun', ['d1', 'd2', 'd4'], 'expedition', { sect_id: 'r2:one', is_retrial: true }])
  view.store.worldMap = null
  assert.match((await renderView(view)).html, /正在读取此宗门所在地区的奖励预览/)
})

test('independent expedition replaces its list with preparation and keeps enemy details in a separate section', async t => {
  const view = setupView('ExpeditionPanel')
  t.after(view.stop)
  let output = await renderView(view)
  assert.match(output.html, /class="sect-map"/)
  assert.doesNotMatch(output.html, /class="sect-dossier|发起征讨 ·/)
  output.nodes.find(node => node.type === 'button' && node.key === 'r1:two').props.onClick()
  await Vue.nextTick()
  output = await renderView(view)
  assert.equal(view.store.targetSectId, 'r1:two')
  assert.match(output.html, /返回宗门列表/)
  assert.doesNotMatch(output.html, /class="sect-map"|class="enemy-intel"|真实宗主情报/)
  assert.ok(output.html.indexOf('发起征讨 ·') < output.html.indexOf('data-child="PartyStrip"'))
  await button(output.nodes, '发起征讨 · 2 行动力').props.onClick()
  assert.deepEqual(view.calls, [['startRun', ['d1', 'd2', 'd4'], 'expedition', { sect_id: 'r1:two' }]])
  button(output.nodes, '敌方情报').props.onClick()
  output = await renderView(view)
  assert.match(output.html, /class="enemy-intel"|真实宗主情报/)
  assert.doesNotMatch(output.html, /发起征讨 ·|data-child="PartyStrip"/)
  button(output.nodes, '返回宗门列表').props.onClick()
  assert.match((await renderView(view)).html, /class="sect-map"/)
  assert.equal(view.store.targetSectId, 'r1:two')
})

test('expedition actions retain stamina, active-run, team, area and busy gates', async t => {
  const view = setupView('ExpeditionPanel', { focused: true })
  t.after(view.stop)
  view.store.targetSectId = 'r1:two'
  await Vue.nextTick()
  async function disabled() { return button((await renderView(view)).nodes, '发起征讨 ·').props.disabled }
  assert.equal(await disabled(), false)
  view.store.busy = true
  assert.equal(await disabled(), true)
  view.store.busy = false
  view.store.resources.stamina = 0
  assert.equal(await disabled(), true)
  view.store.resources.stamina = 8
  view.store.state.active_run = { run_seed: 1 }
  assert.equal(await disabled(), true)
  view.store.state.active_run = null
  view.store.party = ['d1']
  assert.equal(await disabled(), true)
  view.store.party = ['d1', 'd2', 'd3']
  assert.equal(await disabled(), true)
  view.store.party = ['d1', 'd2', 'd4']
  view.selected.value.area = 2
  assert.equal(await disabled(), true)
  assert.deepEqual(view.calls, [])
})

test('section switches reset only the owning modal and reveal the active navigation control', async t => {
  for (const name of ['DutyPanel', 'ExpeditionPanel']) {
    const view = setupView(name)
    t.after(view.stop)
    const actions = []
    view.panel.value = Vue.markRaw({
      closest: selector => { assert.equal(selector, '.modal-body'); return { scrollTo: options => actions.push(['scroll', options]) } },
      querySelector: selector => ({ focus: options => actions.push(['focus', selector, options]), scrollIntoView: options => actions.push(['reveal', selector, options]) }),
    })
    if (name === 'DutyPanel') view.selectTab('assignments')
    else view.selectDetailTab('retrial')
    await Vue.nextTick()
    assert.equal(actions.length, 3)
    assert.deepEqual(actions[0], ['scroll', { top: 0, behavior: 'auto' }])
    assert.deepEqual(actions[1][2], { preventScroll: true })
    assert.deepEqual(actions[2][2], { block: 'nearest', inline: 'nearest', behavior: 'auto' })
    assert.deepEqual(view.calls, [])
  }
})
