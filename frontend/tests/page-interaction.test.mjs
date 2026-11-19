import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { compile, computed, createSSRApp, effectScope, h, nextTick, reactive, ref, watch } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const options = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
const modules = new Map()
async function setupView(file, state, extra = {}) {
  if (!modules.has(file)) {
    const source = await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
    const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
    const syntax = ts.createSourceFile(file, script, ts.ScriptTarget.ES2022, true)
    const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
      ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
      : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
    modules.set(file, { script, names, render: compile(source.match(/<template>([\s\S]*)<\/template>/)[1], { prefixIdentifiers: true }) })
  }
  const module = modules.get(file)
  const store = reactive(state)
  const events = []
  const bindings = {
    computed, ref, watch, onMounted: () => {},
    useGameStore: () => store, defineEmits: () => (...args) => events.push(args),
    characterImage: id => `/characters/${id}.png`, resourceName: id => id,
    number: value => String(value ?? 0), TOWER_SPRITE_IMAGE: '/tower.png',
    api: {}, ...extra,
  }
  const scope = effectScope()
  // Execute the actual setup and template; no browser, copied UI state machine or save mutation.
  const view = scope.run(() => new Function(...Object.keys(bindings),
    `${ts.transpileModule(module.script, { compilerOptions: options }).outputText}\nreturn { ${module.names.join(', ')} }`)(...Object.values(bindings)))
  return { ...view, events, bindings, render: module.render, stop: () => scope.stop() }
}
function flatten(node) {
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!node || typeof node !== 'object') return []
  return [node, ...(Array.isArray(node.children) ? flatten(node.children) : [])]
}
function textOf(node) {
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (!node || typeof node !== 'object') return String(node ?? '')
  return typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? textOf(node.children) : ''
}
async function renderView(view) {
  const roots = []
  const app = createSSRApp({ setup: () => ({ ...view.bindings, ...view }), render(...args) {
    const node = view.render.apply(this, args)
    roots.push(node)
    return node
  } })
  app.component('PanelModal', { props: ['title', 'subtitle', 'wide'], setup(props, { slots }) { return () => {
    const children = slots.default?.() ?? []
    roots.push(children)
    return h('section', { role: 'dialog', 'aria-label': props.title }, children)
  } } })
  for (const name of ['BattleStage', 'PartyStrip', 'PartyHealing', 'GameIcon']) {
    app.component(name, { name, render: () => h('div', { 'data-component': name }) })
  }
  return { html: await renderToString(app), nodes: roots.flatMap(flatten) }
}
function button(nodes, label) {
  const result = nodes.find(node => node.type === 'button' && textOf(node).includes(label))
  assert.ok(result, `missing button: ${label}`)
  return result
}
function conquestState() {
  const unit = id => ({ id, name: `同道${id}`, asset_id: id, health: 100, attack: 8, defense: 3, speed: 2, active: { name: '剑诀', description: '破阵招式' }, passive: { description: '' } })
  const sect = { name: '山河宗', style: '剑修', leader: unit('宗主'), arena_teams: [[unit('守卫')]], loot: { chi_tong: 20 }, material_id: 'chi_tong', special_material_id: 'jade' }
  return {
    slotId: 1, busy: false, status: 'arena', battleResult: null, catalog: {},
    state: { active_run: { run_seed: 123, party: ['a', 'b', 'c', 'd'], selected_party: [], member_hp: { a: 90, b: 80, c: 70, d: 60 }, guard: 100, arena_round: 0, last_battle: null, party_snapshot: { mode: { sect }, combatants: ['a', 'b', 'c', 'd'].map(unit), bonds: [] } } },
  }
}

test('conquest keeps primary actions before battle and opens only the requested detail', async t => {
  const view = await setupView('views/ConquestRun.vue', conquestState())
  t.after(view.stop)
  let output = await renderView(view)
  assert.ok(output.html.indexOf('本场交锋操作') < output.html.indexOf('data-component="BattleStage"'))
  assert.doesNotMatch(output.html, /role="dialog"|破阵招式|chi_tong/)
  button(output.nodes, '下场敌情').props.onClick()
  output = await renderView(view)
  assert.match(output.html, /role="dialog" aria-label="下场敌情"/)
  assert.match(output.html, /破阵招式/)
  assert.doesNotMatch(output.html, /本场上阵顺序|chi_tong/)
  view.openDetail('spoils')
  output = await renderView(view)
  assert.match(output.html, /chi_tong/)
  assert.doesNotMatch(output.html, /破阵招式|本场上阵顺序/)
  view.openDetail('formation')
  output = await renderView(view)
  assert.match(output.html, /本场上阵顺序/)
  assert.doesNotMatch(output.html, /破阵招式/)
  view.openDetail('retreat')
  assert.match((await renderView(view)).html, /行动力不退还/)
})

test('conquest preserves selected order and command guards across playback, settlement and saves', async t => {
  const calls = []
  const view = await setupView('views/ConquestRun.vue', { ...conquestState(), fightArena: async ids => calls.push(ids), settleRun: () => calls.push('settle') })
  t.after(view.stop)
  view.toggle('b')
  view.toggle('d')
  assert.deepEqual(view.selected.value, ['a', 'c', 'd'])
  await view.fight()
  assert.deepEqual(calls, [['a', 'c', 'd']])
  view.store.busy = true
  view.openDetail('formation')
  await view.fight()
  assert.equal(view.detailPanel.value, '')
  view.store.busy = false
  view.openDetail('formation')
  view.playing.value = true
  await nextTick()
  assert.equal(view.detailPanel.value, '')
  view.openDetail('retreat')
  await view.fight()
  assert.equal(view.detailPanel.value, '')
  view.playing.value = false
  await nextTick()
  view.openDetail('opponents')
  view.store.slotId = 2
  await nextTick()
  assert.equal(view.detailPanel.value, '')
  view.openDetail('opponents')
  view.store.status = 'cleared'
  await nextTick()
  assert.equal(view.detailPanel.value, '')
  const output = await renderView(view)
  assert.ok(output.html.indexOf('结算并返回宗门') < output.html.indexOf('data-component="BattleStage"'))
  button(output.nodes, '结算并返回宗门').props.onClick()
  assert.deepEqual(calls, [['a', 'c', 'd'], 'settle'])
})

test('tower preparation puts departure before collapsed bonds and retains tier and stamina restrictions', async t => {
  const calls = []
  const view = await setupView('views/PreparePanel.vue', {
    busy: false, party: ['a'], disciples: [{ id: 'a', template_id: 'hero', busy: false }], resources: { stamina: 3 },
    state: { world: { current_region: 1 }, facility_levels: { tower: 1 }, tower_floor: 20, tower_tiers: { 1: 20 } },
    catalog: { mode: { stamina_cost: 2 }, bonds: { together: { name: '同心', description: '并肩作战', modifiers: [{}], members: ['hero'], requires: 1 } } },
    startRun: (...args) => calls.push(args),
  })
  t.after(view.stop)
  const output = await renderView(view)
  assert.ok(output.html.indexOf('踏上问道之路') < output.html.indexOf('战斗羁绊'))
  assert.match(output.html, /<details class="bonds"><summary>战斗羁绊 · 1 组/)
  button(output.nodes, '踏上问道之路').props.onClick()
  assert.deepEqual(calls, [[['a'], 'tower', { tower_tier: 1 }]])
  view.tier.value = 2
  assert.match(view.reason.value, /升级问道塔/)
  assert.equal(button((await renderView(view)).nodes, '踏上问道之路').props.disabled, true)
  view.tier.value = 1
  view.store.resources.stamina = 0
  assert.match(view.reason.value, /行动力不足/)
})

test('material list filters names and reveals one source without changing exact navigation targets', async t => {
  const matrix = { copper: [{ label: '二重天·赤铜宗', detail: '胜利 +17', available: true, panel: 'expedition', sectId: 'r2:sect_1', kind: 'retrial' }], jade: [{ label: '未开放山门', available: false, kind: 'garrison', blockedReason: '地区未开放' }] }
  const view = await setupView('components/game/MaterialSources.vue', { slotId: 1, revision: 1, catalog: { materials: { copper: '赤铜', jade: '灵玉' } }, loadWorld: async () => {} }, { materialSources: () => matrix })
  t.after(view.stop)
  let output = await renderView(view)
  assert.doesNotMatch(output.html, /role="dialog"|胜利 \+17/)
  view.search.value = '赤'
  output = await renderView(view)
  assert.match(output.html, /赤铜/)
  assert.doesNotMatch(output.html, /灵玉/)
  button(output.nodes, '赤铜').props.onClick()
  output = await renderView(view)
  assert.match(output.html, /role="dialog" aria-label="赤铜"/)
  assert.match(output.html, /胜利 \+17/)
  output.nodes.find(node => node.type === 'button' && textOf(node).trim() === '前往').props.onClick()
  assert.equal(view.store.targetSectId, 'r2:sect_1')
  assert.equal(view.store.productionTarget, 'copper')
  assert.deepEqual(view.events, [['open', 'expedition']])
  view.selectedId.value = 'jade'
  output = await renderView(view)
  assert.equal(button(output.nodes, '地区未开放').props.disabled, true)
  view.store.slotId = 2
  await nextTick()
  assert.equal(view.search.value, '')
  assert.equal(view.selectedId.value, '')
  view.selectedId.value = 'jade'
  delete view.store.catalog.materials.jade
  await nextTick()
  assert.equal(view.selectedId.value, '')
})

test('save creation and import remain collapsed before a long list and preserve existing command parameters', async t => {
  const calls = []
  const view = await setupView('views/SaveSlotsPanel.vue', {
    busy: false, error: null, slotId: 1,
    saves: Array.from({ length: 15 }, (_, i) => ({ slot_id: i + 1, name: `宗门${i + 1}`, updated_at: '2026-11-19T00:00:00Z' })),
    createSave: async name => calls.push(['create', name]), importSave: async payload => calls.push(['import', payload]),
  })
  t.after(view.stop)
  const output = await renderView(view)
  assert.ok(output.html.indexOf('<summary>新立宗门') < output.html.indexOf('class="save-list"'))
  assert.ok(output.html.indexOf('<summary>从备份导入') < output.html.indexOf('class="save-list"'))
  const details = output.nodes.filter(node => node.type === 'details')
  assert.equal(details.length, 2)
  assert.ok(details.every(node => !node.props?.open))
  view.newName.value = '  新山门  '
  await view.create()
  view.importText.value = '{"backup":true}'
  await view.importOne()
  assert.deepEqual(calls, [['create', '新山门'], ['import', { backup: true }]])
  assert.equal(view.newName.value, '')
  assert.equal(view.importText.value, '')
})
