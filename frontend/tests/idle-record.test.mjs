import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'
import { harness, json, snapshot } from './store-harness.mjs'

const transpile = code => ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const formatSource = await readFile(new URL('../src/shared/format.ts', import.meta.url), 'utf8')
const formatCode = ts.transpileModule(formatSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const format = await import(`data:text/javascript;base64,${Buffer.from(formatCode).toString('base64')}`)
const source = await readFile(new URL('../src/views/SectPanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const script = descriptor.scriptSetup.content.replace(/^import .*\r?\n/gm, '')
const syntax = ts.createSourceFile('SectPanel.ts', script, ts.ScriptTarget.ES2022, true)
const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
  ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
  : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
const renderCode = compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true, expressionPlugins: ['typescript'] }).code
const render = new Function('Vue', transpile(renderCode))(Vue)
const citySource = await readFile(new URL('../src/views/CityView.vue', import.meta.url), 'utf8')
const cityScript = parse(citySource).descriptor.scriptSetup.content.replace(/^import .*\r?\n/gm, '')

function setupIncome(store) {
  const bindings = { computed: Vue.computed, nextTick: Vue.nextTick, ref: Vue.ref, useGameStore: () => store,
    defineEmits: () => () => {}, resourceName: id => id, statNames: {}, ...format }
  const scope = Vue.effectScope()
  const view = scope.run(() => new Function(...Object.keys(bindings), `${transpile(script)}\nreturn { ${names.join(', ')} }`)(...Object.values(bindings)))
  return { ...view, ...format, resourceName: id => id, statNames: {}, stop: () => scope.stop() }
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
async function renderIncome(view) {
  const roots = []
  const app = Vue.createSSRApp({ setup: () => view, render(...args) {
    const root = render.apply(this, args)
    roots.push(root)
    return root
  } })
  app.component('GameIcon', { render: () => Vue.h('i') })
  for (const name of ['FacilitiesSection', 'MaterialSources', 'SaveSlotsPanel']) app.component(name, { render: () => Vue.h('div') })
  return { html: await renderToString(app), nodes: roots.flatMap(flatten) }
}
function fixture(revision, elapsedHours, cultivation) {
  const result = snapshot({ revision })
  result.state.idle_record = {
    started_at: '2026-11-19T00:00:00Z', updated_at: '2026-11-19T06:00:00Z',
    elapsed_hours: elapsedHours, dropped_hours: 0, cultivation, spirit_stone: 30, stamina: 2, materials: { chi_tong: 4 },
  }
  return result
}
function settleResult(content, elapsedHours = 0, cultivation = 0) {
  return { ...content, elapsed_hours: elapsedHours, dropped_hours: 0,
    gained: { cultivation, spirit_stone: 0, stamina: 0, materials: {} }, warnings: [] }
}

test('the income record survives login, an online command and a near-zero synchronization without counting the response twice', async t => {
  const initial = fixture(1, 6, 60)
  const session = harness({ 1: initial })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const view = setupIncome(session.store)
  t.after(view.stop)
  let output = await renderIncome(view)
  output.nodes.find(node => node.type === 'button' && textOf(node) === '挂机收益').props.onClick()
  output = await renderIncome(view)
  assert.match(output.html, /累计有效时长 6 小时/)
  assert.match(output.html, /已自动入账/)
  assert.match(output.html, /cultivation \+60/)
  assert.match(output.html, /记录起点/)

  const afterCommand = fixture(2, 6.25, 62.5)
  session.respond('POST', '/saves/1/duty/assign', () => json(afterCommand))
  await session.store.assignDuty('alpha')
  output = await renderIncome(view)
  assert.match(output.html, /累计有效时长 6 小时 15 分钟/)
  assert.match(output.html, /cultivation \+62\.5/)

  const synchronized = fixture(3, 6.25, 62.51)
  session.respond('POST', '/saves/1/settle', () => json(settleResult(synchronized, 3 / 3600, .01)))
  await output.nodes.find(node => node.type === 'button' && textOf(node).includes('同步挂机收益')).props.onClick()
  output = await renderIncome(view)
  assert.match(output.html, /累计有效时长 6 小时 15 分钟/)
  assert.match(output.html, /cultivation \+62\.51/)
  assert.match(output.html, /本次同步新增.*3 秒/s)
  assert.equal(session.store.state.idle_record.cultivation, 62.51)
  assert.equal(session.store.lastSettle.gained.cultivation, .01)
  assert.match(session.store.notice, /同步.*本次新增/)
  assert.doesNotMatch(session.store.notice, /0\.0 小时/)
})

test('refresh reads the persistent record without collecting again or replacing it with a zero-duration receipt', async t => {
  const session = harness({ 1: fixture(1, 6, 60) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const view = setupIncome(session.store)
  t.after(view.stop)
  view.selectTab('income')
  session.saved.set(1, fixture(2, 7, 70))
  await session.store.refresh()
  assert.equal(session.count('POST', '/saves/1/settle'), 1, 'refresh must leave the login settlement as the only POST')
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.match((await renderIncome(view)).html, /累计有效时长 7 小时/)
  assert.equal(session.store.state.idle_record.cultivation, 70)
})

test('city building status shows the backend cumulative record even when the latest synchronization added no time', t => {
  const store = Vue.reactive({
    state: fixture(1, 6, 60).state, disciples: [], resources: {}, status: 'idle',
    catalog: { city: { hotspots: [{ id: 'hall', name: '宗门主殿', panel: 'sect' }] } },
    lastSettle: { elapsed_hours: 0 }, previewFacilities: async () => null, previewRecipes: async () => null,
  })
  const bindings = { computed: Vue.computed, ref: Vue.ref, watch: Vue.watch, useGameStore: () => store,
    defineEmits: () => () => {}, useDayCycle: () => ({}), projectCityActors: () => [], pickNextAction: () => null,
    discipleImage: id => id, resourceName: id => id, ...format }
  const scope = Vue.effectScope()
  t.after(() => scope.stop())
  const view = scope.run(() => new Function(...Object.keys(bindings), `${transpile(cityScript)}\nreturn { buildings }`)(...Object.values(bindings)))
  assert.match(view.buildings.value[0].status, /累计有效时长 6 小时.*已自动入账/)
  store.lastSettle = { elapsed_hours: 3 / 3600 }
  assert.match(view.buildings.value[0].status, /累计有效时长 6 小时/)
})

test('duration labels preserve short intervals and round away floating-point accumulation artifacts', () => {
  assert.equal(format.durationFromHours(.0008), '3 秒')
  assert.equal(format.durationFromHours(1.9999999999999978), '2 小时')
  assert.equal(format.durationFromHours(1 / 60), '1 分钟')
  assert.equal(format.durationFromHours(.00001), '不足 1 秒')
  assert.equal(format.durationFromHours(0), '0 秒')
})

test('rounded incremental gains do not claim that the precise backend cumulative record stopped growing', async t => {
  const session = harness({ 1: fixture(1, 6, 60) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/settle', () => json(settleResult(fixture(2, 6.0001, 60.0003), .0001)))
  await session.store.settle()
  assert.equal(session.store.state.idle_record.cultivation, 60.0003)
  assert.match(session.store.notice, /累计记录保留/)
  assert.doesNotMatch(session.store.notice, /暂无新增|没有新增|无收益/)
})
