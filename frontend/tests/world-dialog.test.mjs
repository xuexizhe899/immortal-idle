import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { Comment, compile, computed, createSSRApp, effectScope, h, nextTick, reactive, ref, watch } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { parse } from '@vue/compiler-sfc'
import ts from 'typescript'

const source = await readFile(new URL('../src/views/WorldPanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const script = descriptor.scriptSetup.content.replace(/^import .*\r?\n/gm, '')
const syntax = ts.createSourceFile('WorldPanel.ts', script, ts.ScriptTarget.ES2022, true)
const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
  ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
  : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
const makeView = new Function('computed', 'ref', 'watch', 'useGameStore', 'defineEmits',
  `${ts.transpileModule(script, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText}\nreturn { ${names.join(', ')} }`)
const render = compile(descriptor.template.content, { prefixIdentifiers: true, onError: error => { throw error } })

function node(region, kind, key, x, y, extra = {}) {
  return { id: `r${region}:${kind}:${key}`, region_id: region, kind, name: `${kind}${key}`, description: '当前据点情报',
    area: 1, x, y, locked: false, reason: '', cleared: false, stamina_cost: kind === 'raid' ? 0 : 2,
    enemy_scale: 1.25, enemy_ids: ['guard'], rewards: { spirit_stone: 7 }, gear_tier: 1, gear_slot: '', ...extra }
}
function map(current = 1) {
  return { current_region: current, invasions: { pending: 2, cap: 3, hours_per_wave: 4 },
    ascension: { held: 1, can_ascend: true, reason: '' },
    regions: [1, 2].map(id => ({ id, name: `地区${id}`, subtitle: '修行山河', selected: current === id, unlocked: true, palette: 'jade',
      areas: [1, 2, 3].map(area => ({ id: area, name: `片区${area}`, unlocked: area === 1 })),
      nodes: [1, 2, 3].flatMap(area => {
        const x = 18 + (area - 1) * 32
        return [
          ...[1, 2, 3].map(index => node(id, 'sect', `${area}:${index}`, x + (index - 2) * 8, 19, { area, sect_id: `r${id}:sect:${area}:${index}`, name: '同名剑宗' })),
          node(id, 'dungeon', `${area}:1`, x - 7, 41, { area, gear_slot: 'weapon' }),
          node(id, 'dungeon', `${area}:2`, x + 7, 41, { area }),
          node(id, 'gate', area, x, 61, { area }), node(id, 'invasion', area, x, 80, { area }),
        ]
      }).concat(node(id, 'raid', 1, 9, 94), node(id, 'tower', 1, 91, 94)),
    })) }
}
function setupView(targetSectId = '') {
  const calls = []
  const loads = []
  const behavior = { startWorld: async () => {}, ascend: async () => {} }
  const world = map()
  const store = reactive({
    slotId: 1, revision: 1, targetSectId, busy: false, worldLoading: false, error: null, worldMap: world,
    resources: { stamina: 5 }, party: ['one'], disciples: [],
    catalog: { enemies: { guard: { name: '守关灵卫' } } },
    state: { active_run: null, world: { current_region: 1 }, facility_levels: { tower: 2 },
      sects: world.regions.flatMap(region => region.nodes.filter(node => node.kind === 'sect').map(node => ({ id: node.sect_id }))) },
    loadWorld: async () => { loads.push(true) },
    settle: async () => { calls.push(['settle']) },
    travelRegion: async (...args) => { calls.push(['travelRegion', ...args]) },
  })
  for (const command of ['startWorld', 'ascend']) store[command] = async (...args) => {
    calls.push([command, ...args])
    store.busy = true
    try { await behavior[command](...args) }
    catch (error) { store.error = error.message }
    finally { store.busy = false }
  }
  const scope = effectScope()
  const view = scope.run(() => makeView(computed, ref, watch, () => store, () => () => {}))
  return { ...view, calls, loads, behavior, stop: () => scope.stop() }
}
async function flushView() { await nextTick(); await nextTick() }
function flatten(node) {
  if (Array.isArray(node)) return node.flatMap(flatten)
  return node && typeof node === 'object' ? [node, ...(Array.isArray(node.children) ? flatten(node.children) : [])] : []
}
function textOf(node) {
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (!node || typeof node !== 'object') return String(node ?? '')
  if (node.type === Comment) return ''
  return typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? node.children.map(textOf).join('') : ''
}
async function renderView(view) {
  const roots = []
  const dialogs = []
  const app = createSSRApp({ setup: () => ({ ...view, resourceName: id => id, number: value => String(value) }), render(...args) {
    const vnode = render.apply(this, args)
    roots.push(vnode)
    return vnode
  } })
  app.component('PanelModal', { name: 'PanelModal', props: ['title', 'subtitle', 'wide'], setup(props, { slots }) { return () => {
    const children = slots.default?.() ?? []
    roots.push(children)
    dialogs.push(props.title)
    return h('section', { role: 'dialog', 'aria-label': props.title }, children)
  } } })
  for (const name of ['ExpeditionPanel', 'PartyStrip', 'PartyHealing']) {
    app.component(name, { name, render: () => h('div', { 'data-component': name }) })
  }
  const html = await renderToString(app)
  return { html, nodes: roots.flatMap(flatten), dialogs }
}
const hasClass = (node, className) => String(node.props?.class ?? '').split(' ').includes(className)
const button = (nodes, text) => nodes.find(node => node.type === 'button' && textOf(node) === text)

test('opening the atlas keeps its first selection quiet and renders all map nodes without stacked details', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  assert.equal(view.showingNode.value, false)
  assert.equal(view.showingSect.value, false)
  assert.equal(view.utility.value, '')
  const { html, nodes, dialogs } = await renderView(view)
  assert.deepEqual(dialogs, [])
  assert.doesNotMatch(html, /data-component="ExpeditionPanel"|data-component="PartyStrip"|首次胜利奖励|消耗一枚升仙令 · 飞升/)
  const marks = nodes.filter(node => node.type === 'button' && hasClass(node, 'map-node'))
  assert.equal(marks.length, 23)
  assert.deepEqual(marks.map(node => node.props.style), view.region.value.nodes.map(node => ({ left: `${node.x}%`, top: `${node.y}%` })))
  assert.ok(marks.every(node => !node.props.disabled && node.props['aria-label']))
  assert.equal(nodes.find(node => hasClass(node, 'map-scroll')).props.tabindex, '0')
  assert.equal(view.loads.length, 1)
  assert.deepEqual(view.calls, [])
})

test('map node handlers open a single detail dialog and closing preserves the map selection and layer', async t => {
  const view = setupView()
  t.after(view.stop)
  const initial = await renderView(view)
  const tower = view.region.value.nodes.find(node => node.kind === 'tower')
  const mark = initial.nodes.find(node => node.type === 'button' && node.props?.title === tower.name)
  mark.props.onClick()
  assert.equal(view.selected.value.id, tower.id)
  assert.equal(view.showingNode.value, true)
  const detail = await renderView(view)
  assert.deepEqual(detail.dialogs, [tower.name])
  assert.doesNotMatch(detail.html, /data-component="PartyStrip"/)
  button(detail.nodes, '出征整备').props.onClick()
  assert.equal(view.nodeTab.value, 'prepare')
  const preparation = await renderView(view)
  assert.match(preparation.html, /data-component="PartyStrip"/)
  assert.doesNotMatch(preparation.html, /首次胜利奖励|定向掉落/)
  preparation.nodes.find(node => node.type?.name === 'PanelModal').props.onClose()
  assert.equal(view.showingNode.value, false)
  assert.equal(view.selected.value.id, tower.id)
  assert.equal(view.region.value.id, 1)
  view.store.revision += 1
  view.store.worldMap = map()
  await flushView()
  assert.equal(view.showingNode.value, false)
  assert.equal(view.selected.value.id, tower.id)
})

test('sect nodes open the exact focused expedition rather than a second list or another same-name sect', async t => {
  const view = setupView()
  t.after(view.stop)
  const sect = view.region.value.nodes.filter(node => node.kind === 'sect')[2]
  view.choose(sect)
  await flushView()
  assert.equal(view.store.targetSectId, sect.sect_id)
  assert.equal(view.showingSect.value, true)
  assert.equal(view.showingNode.value, false)
  const detail = await renderView(view)
  assert.deepEqual(detail.dialogs, ['同名剑宗'])
  const expedition = detail.nodes.find(node => node.type?.name === 'ExpeditionPanel')
  assert.equal(expedition.props.focused, '')
  detail.nodes.find(node => node.type?.name === 'PanelModal').props.onClose()
  view.store.worldMap = map()
  await flushView()
  assert.equal(view.showingSect.value, false)
  assert.equal(view.selected.value.sect_id, sect.sect_id)
  assert.equal(view.store.targetSectId, sect.sect_id)
})

test('explicit material targets remain exact, cross-region targets wait for travel, and missing targets close', async t => {
  const view = setupView('r1:sect:1:2')
  t.after(view.stop)
  assert.equal(view.showingSect.value, true)
  assert.equal(view.selected.value.sect_id, 'r1:sect:1:2')
  view.openUtility('ascension')
  view.store.targetSectId = 'r1:sect:1:3'
  await flushView()
  assert.equal(view.showingSect.value, true)
  assert.equal(view.utility.value, '', 'an explicit target replaces an existing utility dialog')
  view.store.targetSectId = 'r2:sect:1:2'
  await flushView()
  assert.equal(view.showingSect.value, false)
  assert.equal(view.targetElsewhere.value.region.id, 2)
  assert.deepEqual(view.calls, [])
  view.store.state.world.current_region = 2
  view.store.worldMap = map(2)
  await flushView()
  assert.equal(view.selected.value.sect_id, 'r2:sect:1:2')
  assert.equal(view.showingSect.value, true)
  view.store.worldMap.regions = view.store.worldMap.regions.map(region => ({ ...region, nodes: region.nodes.filter(node => node.sect_id !== 'r2:sect:1:2') }))
  await flushView()
  assert.equal(view.showingSect.value, false)
  assert.equal(view.showingNode.value, false)
})

test('locked nodes expose their reason without opening an expedition or bypassing practice restrictions', async t => {
  const view = setupView()
  t.after(view.stop)
  const sect = view.region.value.nodes.find(node => node.kind === 'sect')
  sect.locked = true
  sect.reason = '请先提升宗门大殿'
  view.choose(sect)
  assert.equal(view.showingSect.value, false)
  assert.equal(view.showingNode.value, true)
  const detail = await renderView(view)
  assert.match(detail.html, /请先提升宗门大殿/)
  assert.equal(button(detail.nodes, '查看征讨与驻守').props.disabled, true)
  view.openSect()
  await view.start()
  assert.deepEqual(view.calls, [])
  const raid = view.region.value.nodes.find(node => node.kind === 'raid')
  raid.locked = true
  raid.reason = '暂无待迎击敌情，可选择演练'
  view.choose(raid)
  await view.start()
  assert.deepEqual(view.calls, [])
  await view.start(true)
  assert.deepEqual(view.calls, [['startWorld', raid.id, true, 1]])
})

test('formal challenges retain tier, action costs, party and current-run gates and only submit once while busy', async t => {
  const view = setupView()
  t.after(view.stop)
  const tower = view.region.value.nodes.find(node => node.kind === 'tower')
  view.choose(tower)
  view.towerTier.value = 2
  view.store.resources.stamina = 0
  await view.start()
  view.store.resources.stamina = 5
  view.store.party = []
  await view.start()
  view.store.party = ['one']
  view.store.state.active_run = { run_seed: 12 }
  await view.start()
  assert.deepEqual(view.calls, [])
  assert.equal(view.showingNode.value, false)
  view.store.state.active_run = null
  view.choose(tower)
  let finish
  view.behavior.startWorld = () => new Promise(resolve => { finish = resolve })
  const start = view.start()
  await view.start()
  assert.deepEqual(view.calls, [['startWorld', tower.id, false, 2]])
  finish()
  await start
})

test('enemy and ascension entries replace each other and open selected enemy details through the existing node flow', async t => {
  const view = setupView()
  t.after(view.stop)
  const initial = await renderView(view)
  const invasionEntry = initial.nodes.find(node => node.type === 'button' && textOf(node).startsWith('守山敌情'))
  invasionEntry.props.onClick()
  assert.equal(view.utility.value, 'invasions')
  const enemies = await renderView(view)
  assert.deepEqual(enemies.dialogs, ['守山敌情'])
  assert.match(enemies.html, /每 4 小时积攒一次/)
  button(enemies.nodes, '查看普通迎击').props.onClick()
  assert.equal(view.utility.value, '')
  assert.equal(view.selected.value.kind, 'raid')
  assert.equal(view.showingNode.value, true)
  view.openUtility('ascension')
  assert.equal(view.showingNode.value, false)
  const ascension = await renderView(view)
  assert.deepEqual(ascension.dialogs, ['飞升新境'])
  assert.match(ascension.html, /弟子、装备、强化与旧区驻守全部保留/)
  assert.deepEqual(view.calls, [])
})

test('failed challenge and ascension requests keep their current dialogs and never retry on revision refresh', async t => {
  const view = setupView()
  t.after(view.stop)
  const dungeon = view.region.value.nodes.find(node => node.kind === 'dungeon')
  view.choose(dungeon)
  view.behavior.startWorld = async () => { throw new Error('尚未确认最新进度') }
  await view.start()
  assert.equal(view.showingNode.value, true)
  view.store.revision += 1
  await flushView()
  assert.deepEqual(view.calls, [['startWorld', dungeon.id, false, 1]])
  view.openUtility('ascension')
  view.behavior.ascend = async () => { throw new Error('请恢复连接后刷新') }
  await view.ascend()
  view.store.revision += 1
  await flushView()
  assert.equal(view.utility.value, 'ascension')
  assert.deepEqual(view.calls, [['startWorld', dungeon.id, false, 1], ['ascend']])
  view.store.worldMap.ascension.can_ascend = false
  await view.ascend()
  view.store.worldMap.ascension.can_ascend = true
  view.store.busy = true
  await view.ascend()
  view.store.busy = false
  view.store.state.active_run = { run_seed: 12 }
  await view.ascend()
  assert.equal(view.calls.length, 2)
})

test('save switches, region changes, lost nodes and removed sects close stale dialogs without clearing map data', async t => {
  const view = setupView()
  t.after(view.stop)
  view.choose(view.region.value.nodes.find(node => node.kind === 'dungeon'))
  view.store.slotId = 2
  assert.equal(view.showingNode.value, false)
  assert.equal(view.selectedId.value, '')
  await flushView()
  view.store.worldMap = map()
  await flushView()
  view.openUtility('invasions')
  view.store.state.world.current_region = 2
  assert.equal(view.utility.value, '')
  view.store.worldMap = map(2)
  await flushView()
  const selected = view.region.value.nodes.find(node => node.kind === 'dungeon')
  view.choose(selected)
  view.store.worldMap.regions = view.store.worldMap.regions.map(region => ({ ...region, nodes: region.nodes.filter(node => node.id !== selected.id) }))
  await flushView()
  assert.equal(view.showingNode.value, false)
  const sect = view.region.value.nodes.find(node => node.kind === 'sect')
  view.choose(sect)
  view.store.state.sects = view.store.state.sects.filter(item => item.id !== sect.sect_id)
  await flushView()
  assert.equal(view.showingSect.value, false)
  assert.equal(view.region.value.id, 2)
  assert.equal(view.store.worldMap.regions.length, 2)
})

test('real preparation and utility buttons bind to guarded commands while preserving server previews', async t => {
  const view = setupView()
  t.after(view.stop)
  const dungeon = view.region.value.nodes.find(node => node.kind === 'dungeon')
  const before = JSON.stringify(view.store.worldMap)
  view.choose(dungeon)
  const intel = await renderView(view)
  assert.match(intel.html, /守关灵卫|定向掉落武器/)
  button(intel.nodes, '前往出征整备').props.onClick()
  const preparation = await renderView(view)
  await button(preparation.nodes, '出发挑战 · 2 行动力').props.onClick()
  assert.deepEqual(view.calls, [['startWorld', dungeon.id, false, 1]])
  assert.equal(JSON.stringify(view.store.worldMap), before)
  view.openUtility('ascension')
  const ascension = await renderView(view)
  await button(ascension.nodes, '消耗一枚升仙令 · 飞升').props.onClick()
  assert.deepEqual(view.calls[1], ['ascend'])
})
