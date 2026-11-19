import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { compile, computed, createSSRApp, effectScope, h, markRaw, nextTick, reactive, ref, watch } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const compilerOptions = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
async function moduleUrl(path, imports = {}) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  let output = ts.transpileModule(source, { compilerOptions }).outputText
  for (const [from, to] of Object.entries(imports)) output = output.replaceAll(`'${from}'`, `'${to}'`)
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}
const formatUrl = await moduleUrl('../src/shared/format.ts')
const textUrl = await moduleUrl('../src/presentation/gameText.ts', { '../shared/format': formatUrl })
const { number } = await import(formatUrl)
const { resourceName, snapshotAffixes, snapshotEncounter } = await import(textUrl)
const { equipmentSlotNames } = await import(await moduleUrl('../src/presentation/equipment.ts', {
  '../shared/format': formatUrl, './gameText': textUrl,
}))
const source = await readFile(new URL('../src/views/RunView.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
const syntax = ts.createSourceFile('RunView.ts', script, ts.ScriptTarget.ES2022, true)
const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
  ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
  : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
const bindings = {
  computed, nextTick, ref, watch, number, resourceName, snapshotAffixes, snapshotEncounter, equipmentSlotNames,
  snapshotDiscipleImage: (asset, id) => `/disciples/${asset ?? id}.png`,
  enemyImage: id => `/enemies/${id}.png`,
}
const makeView = new Function(...Object.keys(bindings), 'useGameStore', 'defineEmits',
  `${ts.transpileModule(script, { compilerOptions }).outputText}\nreturn { ${names.join(', ')} }`)
const render = compile(source.match(/<template>([\s\S]*?)<\/template>/)[1], { prefixIdentifiers: true })

function route(kind = 'battle', enemy = 'guard') {
  return { kind, enemy, enemies: kind === 'rest' ? [] : [enemy], power: 80, reward: { spirit_stone: 4 }, description: kind === 'rest' ? '调息恢复气血' : '守住山路' }
}
function activeRun(extra = {}) {
  return {
    run_seed: 123, started_at: '2026-11-19T08:00:00Z', mode: 'tower', tower_tier: 1,
    party: ['disciple-1'], member_hp: { 'disciple-1': 80 }, hp: 80, max_hp: 100,
    nodes: [], choices: [route(), route('rest')], affix_options: [], affixes: ['old_art'],
    pending_loot: { spirit_stone: 12 }, pending_gear: [{ id: 'gear-1', name: '云纹靴', slot: 'boots', tier: 1 }],
    last_battle: null,
    party_snapshot: {
      route_version: 2, mode: { node_count: 20 },
      combatants: [{ id: 'disciple-1', name: '旧局同道', asset_id: 'fixed', health: 100, active: { id: 'old_skill', name: '快照招式' } }],
      enemies: { guard: { name: '旧局守卫', skill: { name: '破阵', description: '降低 def' } } },
      bonds: [{ id: 'bond-1', name: '同心', modifiers: [{ skill: 'old_skill' }] }],
      affix_pool: [
        { id: 'old_art', name: '破军旧卷', group: 'fengrui', description: '旧局伤害提高' },
        { id: 'new_art', name: '回春', group: 'jianshou', description: '恢复气血' },
      ],
    }, ...extra,
  }
}
function setupView(extra = {}) {
  const calls = []
  const behavior = { choose: async () => {}, pickAffix: async () => {} }
  const store = reactive({
    slotId: 1, revision: 1, busy: false, status: 'choosing_node', error: null,
    catalog: { disciples: { current: { name: '新版同道' } }, recipes: {}, weapons: {}, materials: {}, skills: { old_skill: { name: '新版招式' } } },
    disciples: [{ id: 'disciple-1', template_id: 'current' }],
    state: { active_run: activeRun(), tower_floor: 0, tower_tiers: {}, expedition_floor: 0 },
    get run() { return { run: this.state.active_run } },
    get battleResult() { return this.state.active_run?.last_battle ?? null },
    ...extra,
  })
  for (const command of ['choose', 'pickAffix']) store[command] = async value => {
    calls.push([command, value])
    store.busy = true
    try { await behavior[command](value) }
    catch (error) { store.error = error.message }
    finally { store.busy = false }
  }
  const scope = effectScope()
  // Exercise the real setup and Vue scheduler; no copied dialog state machine or browser.
  const view = scope.run(() => makeView(...Object.values(bindings), () => store, () => () => {}))
  return { ...view, calls, behavior, scope, stop: () => scope.stop() }
}
async function flushView() { await nextTick(); await nextTick(); await nextTick() }
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function flatten(node) {
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!node || typeof node !== 'object') return []
  return [node, ...(Array.isArray(node.children) ? flatten(node.children) : [])]
}
function textOf(node) {
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (!node || typeof node !== 'object') return String(node ?? '')
  return typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? node.children.map(textOf).join('') : ''
}
async function renderView(view) {
  const roots = []
  const app = createSSRApp({ setup: () => ({ ...bindings, ...view }), render(...args) {
    const node = render.apply(this, args)
    roots.push(node)
    return node
  } })
  app.component('PanelModal', { props: ['title', 'subtitle', 'wide'], setup(props, { slots }) { return () => {
    const children = slots.default?.() ?? []
    roots.push(children)
    return h('section', { role: 'dialog', 'aria-label': props.title }, children)
  } } })
  for (const name of ['GameIcon', 'GearIcon', 'BattleStage', 'ConquestRun']) {
    app.component(name, { name, render: () => h('div', { 'data-component': name }) })
  }
  const html = await renderToString(app)
  return { html, nodes: roots.flatMap(flatten) }
}

test('the first route opens once, while manual dismissal survives refreshes and replay and restores its trigger', async t => {
  const view = setupView()
  t.after(view.stop)
  assert.equal(view.decisionOpen.value, false)
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  const focusCalls = []
  view.decisionTrigger.value = markRaw({ focus: options => focusCalls.push(options) })
  view.closeDecision()
  view.store.revision += 1
  view.store.state.active_run = structuredClone(activeRun())
  await flushView()
  assert.equal(view.decisionOpen.value, false)
  assert.deepEqual(focusCalls, [{ preventScroll: true }])
  view.playing.value = true
  await flushView()
  view.playing.value = false
  await flushView()
  assert.equal(view.decisionOpen.value, false)
  view.openDecision()
  assert.equal(view.decisionOpen.value, true)
  assert.deepEqual(view.calls, [])
})

test('a child pre watcher starts battle playback before the parent may prompt the new decision', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  view.scope.run(() => watch(() => view.store.battleResult?.id, id => {
    if (id) { view.playing.value = false; view.playing.value = true }
  }))
  view.store.status = 'choosing_affix'
  view.store.state.active_run.nodes.push(route())
  view.store.state.active_run.affix_options = ['new_art']
  view.store.state.active_run.last_battle = { id: '123:1' }
  assert.equal(view.decisionOpen.value, false, 'the old route closes synchronously')
  await flushView()
  assert.equal(view.playing.value, true)
  assert.equal(view.decisionOpen.value, false)
  view.playing.value = false
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  assert.equal(view.decisionKind.value, 'affix')
})

test('finish false followed by a new play true cannot flash or consume the pending prompt', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  view.playing.value = true
  view.store.state.active_run.nodes.push(route())
  await flushView()
  const openings = []
  view.scope.run(() => watch(view.decisionOpen, value => { if (value) openings.push(value) }, { flush: 'sync' }))
  view.playing.value = false
  view.playing.value = true
  await flushView()
  assert.deepEqual(openings, [])
  view.playing.value = false
  await nextTick()
  view.playing.value = true
  await flushView()
  assert.deepEqual(openings, [], 'the extra nextTick must recheck the latest playback state')
  view.playing.value = false
  await flushView()
  assert.deepEqual(openings, [true])
})

test('direct-result playback and peaceful nodes unlock a new prompt without requiring a true playback event', async t => {
  const view = setupView({ busy: true })
  t.after(view.stop)
  await flushView()
  assert.equal(view.decisionOpen.value, false)
  view.openDecision()
  assert.equal(view.decisionOpen.value, false)
  view.store.busy = false
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  view.closeDecision()
  view.store.busy = true
  view.store.state.active_run.nodes.push(route())
  view.store.state.active_run.last_battle = { id: '123:1', events: [{ sequence: 1 }] }
  view.store.status = 'choosing_affix'
  view.store.state.active_run.affix_options = ['new_art']
  await flushView()
  assert.equal(view.decisionOpen.value, false)
  view.store.busy = false
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  assert.equal(view.decisionKind.value, 'affix')
  view.store.status = 'choosing_node'
  view.store.state.active_run.affix_options = []
  assert.equal(view.decisionOpen.value, false)
  await flushView()
  assert.equal(view.decisionKind.value, 'route')
  assert.equal(view.decisionOpen.value, true)
  view.closeDecision()
  view.store.state.active_run.nodes.push(route('rest'))
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  assert.equal(view.lastWasPeaceful.value, true)
  assert.equal(view.store.battleResult.id, '123:1', 'peaceful nodes retain the previous battle')
})

test('route and affix commands preserve original values and reject duplicates, invalid options and playback input', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  const routeRequest = deferred()
  view.behavior.choose = () => routeRequest.promise
  const choosing = view.chooseRoute(1)
  await view.chooseRoute(0)
  await view.chooseAffix('new_art')
  assert.deepEqual(view.calls, [['choose', 1]])
  assert.equal(view.canDecide.value, false)
  routeRequest.resolve()
  await choosing
  await view.chooseRoute(-1)
  await view.chooseRoute(20)
  view.store.status = 'choosing_affix'
  view.store.state.active_run.affix_options = ['new_art']
  await flushView()
  const affixRequest = deferred()
  view.behavior.pickAffix = () => affixRequest.promise
  await view.chooseAffix('missing')
  const picking = view.chooseAffix('new_art')
  await view.chooseAffix('new_art')
  await view.chooseRoute(0)
  assert.deepEqual(view.calls, [['choose', 1], ['pickAffix', 'new_art']])
  affixRequest.resolve()
  await picking
  view.playing.value = true
  await view.chooseAffix('new_art')
  assert.equal(view.calls.length, 2)
})

test('an uncertain or failed command keeps the same decision available without an automatic retry', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  view.behavior.choose = async () => { throw new Error('进度尚未确认，请刷新') }
  const before = JSON.stringify(view.store.state.active_run)
  await view.chooseRoute(0)
  await flushView()
  assert.equal(view.store.error, '进度尚未确认，请刷新')
  assert.equal(view.decisionOpen.value, true)
  assert.equal(view.canDecide.value, true)
  view.store.revision += 1
  await flushView()
  assert.deepEqual(view.calls, [['choose', 0]])
  assert.equal(JSON.stringify(view.store.state.active_run), before)
})

test('settlement, save changes and new runs cancel old prompts and reset the local information tab', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  view.infoTab.value = 'arts'
  view.store.status = 'cleared'
  assert.equal(view.decisionOpen.value, false)
  await flushView()
  assert.equal(view.decisionKey.value, '')
  view.store.state.active_run = null
  view.store.status = 'idle'
  await flushView()
  assert.equal(view.infoTab.value, 'loot')
  assert.equal(view.decisionOpen.value, false)
  view.store.state.active_run = activeRun()
  view.store.status = 'choosing_node'
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  view.closeDecision()
  view.infoTab.value = 'bonds'
  view.store.busy = true
  view.store.slotId = 2
  assert.equal(view.infoTab.value, 'loot')
  assert.equal(view.decisionOpen.value, false)
  await flushView()
  assert.equal(view.decisionOpen.value, false)
  view.store.busy = false
  await flushView()
  assert.equal(view.decisionOpen.value, true)
  view.infoTab.value = 'arts'
  view.store.state.active_run = activeRun({ run_seed: 999 })
  assert.equal(view.decisionOpen.value, false)
  assert.equal(view.infoTab.value, 'loot')
  await flushView()
  assert.equal(view.decisionOpen.value, true)
})

test('leaving a decision before its scheduled prompt cannot reopen it and sect runs retain their own view', async t => {
  const abandoned = setupView()
  const sect = setupView()
  t.after(abandoned.stop)
  t.after(sect.stop)
  abandoned.store.state.active_run = null
  abandoned.store.status = 'idle'
  sect.store.state.active_run.sect_id = 'sect-1'
  await flushView()
  assert.equal(abandoned.decisionOpen.value, false)
  assert.equal(sect.decisionOpen.value, false)
  assert.equal(sect.decisionKind.value, '')
  sect.openDecision()
  await sect.chooseRoute(0)
  await sect.chooseAffix('new_art')
  assert.deepEqual(sect.calls, [])
  const { html } = await renderView(sect)
  assert.match(html, /data-component="ConquestRun"/)
  assert.doesNotMatch(html, /role="dialog"|此行记录|下一步行动/)
})

test('the real template places the decision trigger above battle, tabs below, and binds each original route index', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  const { html, nodes } = await renderView(view)
  assert.ok(html.indexOf('下一步行动') < html.indexOf('data-component="BattleStage"'))
  assert.ok(html.indexOf('此行记录') > html.indexOf('data-component="BattleStage"'))
  assert.match(html, /role="dialog" aria-label="选择路线"/)
  const buttons = nodes.filter(node => node.type === 'button')
  const routes = buttons.filter(node => String(node.props?.class).split(' ').includes('node-card'))
  assert.equal(routes.length, 2)
  await routes[1].props.onClick()
  assert.deepEqual(view.calls, [['choose', 1]])
  buttons.find(node => textOf(node).startsWith('战斗羁绊')).props.onClick()
  assert.equal(view.infoTab.value, 'bonds')
  buttons.find(node => textOf(node).startsWith('已悟道法')).props.onClick()
  assert.equal(view.infoTab.value, 'arts')
  const stage = nodes.find(node => node.type?.name === 'BattleStage')
  stage.props.onPlaying(true)
  assert.equal(view.playing.value, true)
  view.closeDecision()
  await flushView()
  const locked = await renderView(view)
  const trigger = locked.nodes.find(node => node.type === 'button' && node.props?.['aria-haspopup'] === 'dialog')
  assert.equal(trigger.props.disabled, true)
})

test('information tabs and affix buttons use fixed snapshots and never mutate saved battle or rewards', async t => {
  const view = setupView()
  t.after(view.stop)
  await flushView()
  view.closeDecision()
  const before = JSON.stringify(view.store.state.active_run)
  for (const [tab, content, excluded] of [
    ['loot', '云纹靴', '同心'], ['bonds', '快照招式', '破军旧卷'], ['arts', '破军旧卷', '云纹靴'],
  ]) {
    view.infoTab.value = tab
    const { html } = await renderView(view)
    assert.match(html, new RegExp(content))
    assert.doesNotMatch(html, new RegExp(excluded))
    assert.doesNotMatch(html, /新版同道|新版招式/)
  }
  assert.equal(view.party.value[0].name, '旧局同道')
  assert.equal(view.routeChoices.value[0].roster[0].name, '旧局守卫')
  assert.equal(view.affixDefinitions.value.old_art.name, '破军旧卷')
  assert.equal(JSON.stringify(view.store.state.active_run), before)
  view.store.status = 'choosing_affix'
  view.store.state.active_run.affix_options = ['new_art']
  await flushView()
  const { nodes, html } = await renderView(view)
  assert.match(html, /role="dialog" aria-label="领悟道法"/)
  const affix = nodes.find(node => node.type === 'button' && String(node.props?.class).split(' ').includes('affix-card'))
  await affix.props.onClick()
  assert.deepEqual(view.calls, [['pickAffix', 'new_art']])
})

test('both tower entry paths explain failed-run gear recovery and retain the actual pending drops', async t => {
  for (const mapped of [false, true]) {
    const view = setupView({ status: 'defeated' })
    t.after(view.stop)
    const run = view.store.state.active_run
    run.end_reason = 'round_limit'
    run.choices = []
    if (mapped) run.party_snapshot.mode.world_node = { id: 'r1:tower', kind: 'tower', name: '问道塔' }
    const before = JSON.stringify(run)
    const { html } = await renderView(view)
    assert.match(view.lootNote.value, /装备.*全部带回.*资源.*折算/)
    assert.match(view.endingDescription.value, /二十轮已尽.*装备.*全部带回.*资源.*折算/)
    assert.match(html, /云纹靴/)
    assert.equal(JSON.stringify(run), before)
    assert.deepEqual(view.calls, [])
    run.practice = true
    assert.match(view.lootNote.value, /演练不发放/)
    assert.match(view.endingDescription.value, /演练不发放/)
    assert.doesNotMatch(view.endingDescription.value, /全部带回/)
  }
})

test('individual vitals show actual health after an affix without treating the departure snapshot as its current limit', async t => {
  const view = setupView()
  t.after(view.stop)
  const run = view.store.state.active_run
  run.member_hp['disciple-1'] = 107
  run.hp = 107
  run.max_hp = 107
  const before = JSON.stringify(run)
  await flushView()
  view.closeDecision()
  const { html, nodes } = await renderView(view)
  const vitals = nodes.find(node => node.type === 'details' && node.props?.class === 'party-vitals')
  assert.ok(vitals)
  assert.match(textOf(vitals), /气血 107/)
  assert.doesNotMatch(textOf(vitals), /107\s*\/\s*100/)
  assert.equal(flatten(vitals).some(node => node.props?.class === 'progress-track'), false)
  assert.match(html, /107 \/ 107/)
  assert.equal(JSON.stringify(run), before)
  assert.deepEqual(view.calls, [])
})
