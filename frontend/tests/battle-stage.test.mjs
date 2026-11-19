import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import ts from 'typescript'

const compilerOptions = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
async function importModule(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, { compilerOptions }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
}
const bindings = {
  computed, ref, watch,
  defineAsyncComponent: () => ({}),
  ...await importModule('../src/rendering/battlePlayback.ts'),
  ...await importModule('../src/shared/format.ts'),
  characterImage: id => `/characters/${id}.png`,
  TOWER_SCENE_IMAGE: '/tower.png',
}
const source = await readFile(new URL('../src/rendering/BattleStage.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
const syntax = ts.createSourceFile('BattleStage.ts', script, ts.ScriptTarget.ES2022, true)
const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
  ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
  : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
const makeView = new Function(...Object.keys(bindings), 'defineProps', 'defineEmits', 'onMounted', 'onUnmounted', 'window', 'document',
  `${ts.transpileModule(script, { compilerOptions }).outputText}\nreturn { ${names.join(', ')} }`)

function clock() {
  let now = 0, sequence = 0
  const pending = new Map()
  return {
    setTimeout(callback, delay) {
      const id = ++sequence
      pending.set(id, { callback, at: now + delay })
      return id
    },
    clearTimeout: id => pending.delete(id),
    get size() { return pending.size },
    callbacks: () => [...pending.values()].map(item => item.callback),
    async next() {
      const [id, item] = [...pending].sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0] ?? []
      assert.ok(item, 'the next playback phase has a scheduled timer')
      pending.delete(id)
      now = item.at
      item.callback()
      await flushView()
    },
  }
}
function setupStage({ hidden = false, reduced = false } = {}) {
  const timers = clock(), emitted = [], mounted = [], unmounted = []
  const mediaListeners = new Set(), visibilityListeners = new Set()
  const media = {
    matches: reduced,
    addEventListener: (type, listener) => { assert.equal(type, 'change'); mediaListeners.add(listener) },
    removeEventListener: (type, listener) => { assert.equal(type, 'change'); mediaListeners.delete(listener) },
  }
  const document = {
    hidden,
    addEventListener: (type, listener) => { assert.equal(type, 'visibilitychange'); visibilityListeners.add(listener) },
    removeEventListener: (type, listener) => { assert.equal(type, 'visibilitychange'); visibilityListeners.delete(listener) },
  }
  const window = {
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
    matchMedia: query => { assert.equal(query, '(prefers-reduced-motion: reduce)'); return media },
  }
  const props = reactive({ party: [], result: null })
  const scope = effectScope()
  // Run the actual setup and Vue watchers; only browser time and lifecycle are controlled.
  const view = scope.run(() => makeView(...Object.values(bindings), () => props, () => (...event) => emitted.push(event),
    callback => mounted.push(callback), callback => unmounted.push(callback), window, document))
  mounted.forEach(callback => callback())
  let stopped = false
  return {
    ...view, props, timers, emitted, mediaListeners, visibilityListeners,
    setHidden(value) { document.hidden = value; visibilityListeners.forEach(listener => listener()) },
    setReduced(value) { media.matches = value; mediaListeners.forEach(listener => listener()) },
    stop() {
      if (stopped) return
      stopped = true
      unmounted.forEach(callback => callback())
      scope.stop()
    },
  }
}
function unit(id, hp, shield = 0) {
  return {
    id, name: id, side: id === 'ally' ? 'ally' : 'enemy', slot: 0,
    template_id: id, asset_id: id, hp, max_hp: 120, shield,
    attack: 23, defense: 7, speed: 11, cooldown: 0, statuses: [], affixes: [],
  }
}
function battle(id = 'battle-1') {
  const initial = [unit('ally', 97, 5), unit('enemy', 120, 11)]
  const first = [unit('ally', 97, 5), unit('enemy', 103, 7)]
  const second = [unit('ally', 106, 5), unit('enemy', 103, 7)]
  const final = [unit('ally', 94), unit('enemy', 103, 7)]
  return {
    id, won: true, reason: 'victory', rounds: 1, damage: 12, healed: 9, hp_after: 94,
    node: { kind: 'battle' }, initial_units: initial, final_units: structuredClone(final),
    events: [
      { sequence: 1, round: 1, actor_id: 'ally', skill_id: 'basic_attack', skill_name: '挥剑', vfx: 'strike', bonds: [],
        effects: [{ target_id: 'enemy', kind: 'damage', amount: 17, absorbed: 4 }], units: first },
      { sequence: 2, round: 1, actor_id: 'ally', skill_id: 'heal', skill_name: '回春', vfx: 'heal', bonds: [],
        effects: [{ target_id: 'ally', kind: 'heal', amount: 9 }], units: second },
      { sequence: 3, round: 1, actor_id: 'enemy', skill_id: 'basic_attack', skill_name: '反击', vfx: 'strike', bonds: [],
        effects: [{ target_id: 'ally', kind: 'damage', amount: 12, absorbed: 5 }], units: final },
    ],
  }
}
async function flushView() { await nextTick(); await nextTick() }
async function start(view, result = battle()) {
  view.props.result = result
  await flushView()
}
function assertFinished(view) {
  assert.equal(view.phase.value, 'idle')
  assert.equal(view.playing.value, false)
  assert.equal(view.cursor.value, view.props.result.events.length)
  assert.strictEqual(view.units.value, view.props.result.final_units)
  assert.equal(view.timers.size, 0)
  assert.deepEqual(view.emitted.at(-1), ['playing', false])
}

test('windup keeps the previous server snapshot and contact reveals the recorded damage and healing', async t => {
  const view = setupStage(); t.after(view.stop)
  const result = battle(), before = structuredClone(result)
  await start(view, result)

  assert.equal(view.playing.value, true)
  assert.equal(view.phase.value, 'windup')
  assert.equal(view.cursor.value, 0)
  assert.strictEqual(view.units.value, view.props.result.initial_units)
  assert.equal(view.isTarget('enemy'), false)

  await view.timers.next()
  assert.equal(view.phase.value, 'contact')
  assert.strictEqual(view.units.value, view.props.result.events[0].units)
  assert.equal(view.isTarget('enemy'), true)
  assert.equal(view.units.value.find(item => item.id === 'enemy').hp, 103)
  assert.equal(view.units.value.find(item => item.id === 'enemy').shield, 7)

  await view.timers.next()
  assert.equal(view.phase.value, 'recover')
  assert.strictEqual(view.units.value, view.props.result.events[0].units)
  await view.timers.next()
  assert.equal(view.phase.value, 'windup')
  assert.equal(view.cursor.value, 1)
  assert.strictEqual(view.units.value, view.props.result.events[0].units)
  assert.equal(view.isTarget('ally'), false)

  await view.timers.next()
  assert.equal(view.phase.value, 'contact')
  assert.strictEqual(view.units.value, view.props.result.events[1].units)
  assert.equal(view.units.value.find(item => item.id === 'ally').hp, 106)
  for (let step = 0; view.playing.value && step < 15; step++) await view.timers.next()
  assertFinished(view)
  assert.deepEqual(result, before, 'playback does not rewrite server health, effects or results')
})

test('skipping clears every phase timer and a callback already queued cannot resume playback', async t => {
  const view = setupStage(); t.after(view.stop)
  await start(view)
  const abandoned = view.timers.callbacks()
  assert.ok(abandoned.length >= 2, 'both the phase timer and watchdog are active')
  view.finish()
  assertFinished(view)
  for (const callback of abandoned) callback()
  await flushView()
  assertFinished(view)
})

test('a new battle invalidates old phase and watchdog callbacks without interrupting its own windup', async t => {
  const view = setupStage(); t.after(view.stop)
  await start(view)
  const abandoned = view.timers.callbacks()
  const next = battle('battle-2')
  next.initial_units[0].hp = 81
  await start(view, next)
  const activeTimers = view.timers.size
  for (const callback of abandoned) callback()
  await flushView()

  assert.equal(view.playing.value, true)
  assert.equal(view.phase.value, 'windup')
  assert.equal(view.cursor.value, 0)
  assert.strictEqual(view.units.value, view.props.result.initial_units)
  assert.equal(view.units.value[0].hp, 81)
  assert.equal(view.timers.size, activeTimers)
  assert.deepEqual(view.emitted.at(-1), ['playing', true])
  await view.timers.next()
  assert.equal(view.phase.value, 'contact')
  assert.strictEqual(view.units.value, view.props.result.events[0].units)
})

test('reduced motion, a hidden document and result-only mode never acquire a playback lock', async t => {
  for (const preference of [{ reduced: true }, { hidden: true }, { mode: 'result' }]) {
    const view = setupStage(preference); t.after(view.stop)
    if (preference.mode) { view.mode.value = preference.mode; await flushView() }
    await start(view)
    assertFinished(view)
    assert.equal(view.emitted.some(([event, value]) => event === 'playing' && value), false)
  }
})

test('switching to reduced motion or the background releases contact and does not replay when restored', async t => {
  for (const preference of ['reduced', 'hidden']) {
    const view = setupStage(); t.after(view.stop)
    await start(view)
    await view.timers.next()
    assert.equal(view.phase.value, 'contact')
    const abandoned = view.timers.callbacks()
    if (preference === 'reduced') view.setReduced(true)
    else view.setHidden(true)
    assertFinished(view)
    for (const callback of abandoned) callback()
    if (preference === 'reduced') view.setReduced(false)
    else view.setHidden(false)
    await flushView()
    assertFinished(view)
  }
})

test('unmount clears phase timers and listeners while leaving an exact final frame', async t => {
  const view = setupStage(); t.after(view.stop)
  await start(view)
  const abandoned = view.timers.callbacks()
  assert.equal(view.mediaListeners.size, 1)
  assert.equal(view.visibilityListeners.size, 1)
  view.stop()
  assertFinished(view)
  assert.equal(view.mediaListeners.size, 0)
  assert.equal(view.visibilityListeners.size, 0)
  for (const callback of abandoned) callback()
  await flushView()
  assertFinished(view)
})
