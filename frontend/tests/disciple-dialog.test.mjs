import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { computed, effectScope, markRaw, nextTick, reactive, ref, watch } from 'vue'
import ts from 'typescript'

function compile(script) {
  return ts.transpileModule(script.replace(/^import .*\r?\n/gm, ''), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  }).outputText
}

const codexSource = await readFile(new URL('../src/views/CodexPanel.vue', import.meta.url), 'utf8')
const codexScript = compile(codexSource.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1])
const makeCodex = new Function('computed', 'nextTick', 'ref', 'watch', 'useGameStore', 'defineProps', `${codexScript}
  return { tab, filter, search, roster, selected, selectedId, selectedIndex, detailOpen, detailTab,
    detailModal, openDisciple, closeDisciple, changeDisciple, onDetailKey, goTrain }`)

function codexStore() {
  const loads = []
  const disciples = ['alpha', 'beta', 'gamma'].map((template_id, index) => ({
    id: `disciple-${index + 1}`, template_id, level: 1, realm: 1,
    injury_stacks: 0, busy: false, stats: {},
  }))
  const store = reactive({
    slotId: 1, revision: 1, disciples, party: ['disciple-2'],
    state: { duty_slots: [], unlocks: ['alpha', 'beta', 'gamma'] },
    catalog: { rules: { max_party: 6 }, disciples: {
      alpha: { name: '甲弟子', lean: 'attack', base_stats: {}, bonds: [] },
      beta: { name: '乙弟子', lean: 'defense', base_stats: {}, bonds: [] },
      gamma: { name: '丙弟子', lean: 'attack', base_stats: {}, bonds: [] },
    }, recipes: {}, bonds: {} },
    training: null, trainingFor: '', trainingLoading: false,
    loadTraining: async id => { loads.push(id) },
  })
  return { store, loads }
}

function setupCodex(props = {}) {
  const { store, loads } = codexStore()
  const reactiveProps = reactive(props)
  const scope = effectScope()
  // Execute the real setup with Vue watchers instead of reimplementing selection logic.
  const view = scope.run(() => makeCodex(computed, nextTick, ref, watch, () => store, () => reactiveProps))
  return { ...view, store, loads, props: reactiveProps, stop: () => scope.stop() }
}

async function flushView() { await nextTick(); await nextTick() }

function keyEvent(key, extra = {}) {
  return {
    key, defaultPrevented: false, shiftKey: false, altKey: false, ctrlKey: false, metaKey: false,
    target: { closest: () => null },
    preventDefault() { this.defaultPrevented = true },
    ...extra,
  }
}

test('opening the roster alone neither opens a detail dialog nor requests the first disciple preview', async t => {
  const view = setupCodex()
  t.after(view.stop)
  await flushView()
  assert.equal(view.detailOpen.value, false)
  assert.equal(view.selected.value, undefined)
  assert.deepEqual(view.loads, [])
  view.store.revision += 1
  await flushView()
  assert.deepEqual(view.loads, [])
})

test('explicit disciple opening selects only the requested disciple without changing formation', async t => {
  const view = setupCodex()
  t.after(view.stop)
  const party = [...view.store.party]
  view.openDisciple('disciple-3')
  await flushView()
  assert.equal(view.detailOpen.value, true)
  assert.equal(view.selected.value.id, 'disciple-3')
  assert.equal(view.detailTab.value, 'overview')
  assert.deepEqual(view.loads, ['disciple-3'])
  assert.deepEqual([...view.store.party], party)
})

test('previous and next wrap within the filtered roster and retain the current detail section', async t => {
  const view = setupCodex()
  t.after(view.stop)
  view.filter.value = 'attack'
  view.openDisciple('disciple-1', 'equipment')
  await flushView()
  assert.deepEqual(view.roster.value.map(item => item.id), ['disciple-1', 'disciple-3'])
  view.changeDisciple(-1)
  await flushView()
  assert.equal(view.selected.value.id, 'disciple-3')
  assert.equal(view.selectedIndex.value, 1)
  assert.equal(view.detailTab.value, 'equipment')
  view.changeDisciple(1)
  await flushView()
  assert.equal(view.selected.value.id, 'disciple-1')
  assert.equal(view.detailTab.value, 'equipment')
  assert.deepEqual(view.loads, ['disciple-1', 'disciple-3', 'disciple-1'])
})

test('a single filtered disciple stays selected and an empty result closes the detail', async t => {
  const view = setupCodex()
  t.after(view.stop)
  view.filter.value = 'defense'
  view.openDisciple('disciple-2')
  await flushView()
  view.changeDisciple(-1)
  view.changeDisciple(1)
  await flushView()
  assert.equal(view.selected.value.id, 'disciple-2')
  assert.deepEqual(view.loads, ['disciple-2'])
  view.search.value = '不存在的弟子'
  await flushView()
  assert.equal(view.roster.value.length, 0)
  assert.equal(view.detailOpen.value, false)
  view.changeDisciple(1)
  await flushView()
  assert.deepEqual(view.loads, ['disciple-2'])
})

test('closing the detail stops revision-driven preview loads until an explicit reopen', async t => {
  const view = setupCodex()
  t.after(view.stop)
  view.openDisciple('disciple-1')
  await flushView()
  view.closeDisciple()
  await flushView()
  view.store.revision += 1
  await flushView()
  assert.deepEqual(view.loads, ['disciple-1'])
  view.openDisciple('disciple-1')
  await flushView()
  assert.deepEqual(view.loads, ['disciple-1', 'disciple-1'])
})

test('recruitment training opens the matching owned disciple directly in the training section', async t => {
  const view = setupCodex()
  t.after(view.stop)
  view.tab.value = 'recruit'
  view.filter.value = 'defense'
  view.search.value = '乙'
  await flushView()
  view.goTrain('gamma')
  await flushView()
  assert.equal(view.tab.value, 'roster')
  assert.equal(view.filter.value, 'all')
  assert.equal(view.search.value, '')
  assert.equal(view.selected.value.id, 'disciple-3')
  assert.equal(view.detailOpen.value, true)
  assert.equal(view.detailTab.value, 'training')
})

test('a valid initial disciple opens directly while an invalid identity never opens a fallback', async t => {
  const invalid = setupCodex({ initialDiscipleId: 'missing' })
  const valid = setupCodex({ initialDiscipleId: 'disciple-2' })
  t.after(invalid.stop)
  t.after(valid.stop)
  await flushView()
  assert.equal(invalid.detailOpen.value, false)
  assert.equal(invalid.selected.value, undefined)
  assert.deepEqual(invalid.loads, [])
  assert.equal(valid.detailOpen.value, true)
  assert.equal(valid.selected.value.id, 'disciple-2')
  assert.deepEqual(valid.loads, ['disciple-2'])
  valid.props.initialDiscipleId = 'disciple-3'
  await flushView()
  assert.equal(valid.selected.value.id, 'disciple-3')
})

test('switching saves or removing the selected disciple closes the current detail', async t => {
  const switched = setupCodex()
  const removed = setupCodex()
  t.after(switched.stop)
  t.after(removed.stop)
  switched.openDisciple('disciple-1')
  removed.openDisciple('disciple-2')
  await flushView()
  switched.store.slotId = 2
  removed.store.disciples = removed.store.disciples.filter(item => item.id !== 'disciple-2')
  await flushView()
  assert.equal(switched.detailOpen.value, false)
  assert.equal(switched.selectedId.value, '')
  assert.equal(removed.detailOpen.value, false)
  assert.equal(removed.selected.value, undefined)
})

test('changing disciples or detail sections resets only the detail scroll position', async t => {
  const view = setupCodex()
  t.after(view.stop)
  let resets = 0
  view.detailModal.value = { resetScroll: () => { resets += 1 } }
  view.openDisciple('disciple-1')
  await flushView()
  assert.equal(resets, 1)
  view.changeDisciple(1)
  await flushView()
  assert.equal(resets, 2)
  view.detailTab.value = 'arts'
  await flushView()
  assert.equal(resets, 3)
})

test('arrow navigation ignores input and editable targets, shortcuts, and already handled events', async t => {
  const view = setupCodex()
  t.after(view.stop)
  view.openDisciple('disciple-1')
  await flushView()
  for (const tag of ['INPUT', 'SELECT', 'TEXTAREA', 'CONTENTEDITABLE']) {
    const event = keyEvent('ArrowRight', { target: { closest: () => ({ tagName: tag }) } })
    view.onDetailKey(event)
    assert.equal(event.defaultPrevented, false)
    assert.equal(view.selectedId.value, 'disciple-1')
  }
  for (const modifier of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey', 'defaultPrevented']) {
    view.onDetailKey(keyEvent('ArrowRight', { [modifier]: true }))
    assert.equal(view.selectedId.value, 'disciple-1')
  }
  const right = keyEvent('ArrowRight')
  view.onDetailKey(right)
  assert.equal(right.defaultPrevented, true)
  assert.equal(view.selectedId.value, 'disciple-2')
  view.onDetailKey(keyEvent('ArrowLeft'))
  assert.equal(view.selectedId.value, 'disciple-1')
  const unrelated = keyEvent('Enter')
  view.onDetailKey(unrelated)
  assert.equal(unrelated.defaultPrevented, false)
})

const modalSource = await readFile(new URL('../src/components/ui/PanelModal.vue', import.meta.url), 'utf8')
const modalModule = compile(modalSource.match(/<script lang="ts">([\s\S]*?)<\/script>/)[1])
const modalScript = compile(modalSource.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1])

function modalEnvironment(overflow = 'auto') {
  const listeners = new Set()
  const document = { dialogs: [], activeElement: null, body: { style: { overflow } },
    querySelectorAll: () => document.dialogs.filter(dialog => dialog.isConnected) }
  const window = {
    addEventListener: (type, handler) => { if (type === 'keydown') listeners.add(handler) },
    removeEventListener: (type, handler) => { if (type === 'keydown') listeners.delete(handler) },
  }
  // The ordinary script is evaluated once per environment, sharing the real modal counter.
  const instantiate = new Function('nextTick', 'ref', 'document', 'window', `${modalModule}
    return function create({onMounted, onUnmounted, defineProps, defineEmits, defineExpose}) {
      ${modalScript}
      return { sheet, body }
    }`)(nextTick, ref, document, window)

  function element(parent = null, visible = true) {
    return markRaw({ parent, connected: true, inert: false, attributes: {}, controls: [],
      get isConnected() { return this.connected && (!this.parent || this.parent.isConnected) },
      getClientRects: () => visible ? [{}] : [],
      setAttribute(name, value) { this.attributes[name] = value },
      contains(target) { for (let item = target; item; item = item.parent) if (item === this) return true; return false },
      focus() { document.activeElement = this },
      querySelectorAll() { return this.controls },
    })
  }

  function create() {
    const mounted = [], unmounted = [], events = []
    let exposed
    const view = instantiate({
      onMounted: callback => mounted.push(callback), onUnmounted: callback => unmounted.push(callback),
      defineProps: () => ({ title: '弟子详情' }), defineEmits: () => (...args) => events.push(args),
      defineExpose: value => { exposed = value },
    })
    const sheet = element()
    sheet.controls = [element(sheet), element(sheet)]
    const body = markRaw({ scrollTop: 240 })
    view.sheet.value = sheet
    view.body.value = body
    return { sheet, body, events, exposed,
      attach() { document.dialogs.push(sheet) },
      mount: () => Promise.all(mounted.map(callback => callback())),
      unmount() {
        sheet.connected = false
        document.dialogs = document.dialogs.filter(dialog => dialog !== sheet)
        for (const callback of unmounted) callback()
      },
    }
  }
  return { document, element, create, listeners,
    dispatch(event) { for (const callback of [...listeners]) callback(event) },
  }
}

test('nested modal Escape and Tab belong only to the top dialog and restore the parent focus', async () => {
  const env = modalEnvironment('scroll')
  const trigger = env.element()
  trigger.focus()
  const parent = env.create()
  parent.attach()
  await parent.mount()
  const card = parent.sheet.controls[1]
  card.focus()
  const child = env.create()
  child.attach()
  await child.mount()
  assert.equal(parent.sheet.inert, true)
  assert.equal(parent.sheet.attributes['aria-modal'], 'false')
  assert.equal(child.sheet.inert, false)
  assert.equal(env.document.body.style.overflow, 'hidden')
  child.sheet.controls[1].focus()
  const tab = keyEvent('Tab')
  env.dispatch(tab)
  assert.equal(tab.defaultPrevented, true)
  assert.equal(env.document.activeElement, child.sheet.controls[0])
  const escape = keyEvent('Escape')
  env.dispatch(escape)
  assert.deepEqual(parent.events, [])
  assert.deepEqual(child.events, [['close']])
  child.unmount()
  assert.equal(env.document.activeElement, card)
  assert.equal(parent.sheet.inert, false)
  assert.equal(parent.sheet.attributes['aria-modal'], 'true')
  assert.equal(env.document.body.style.overflow, 'hidden')
  parent.unmount()
  assert.equal(env.document.activeElement, trigger)
  assert.equal(env.document.body.style.overflow, 'scroll')
  assert.equal(env.listeners.size, 0)
})

test('initial direct detail keeps the child on top even when the child mounts before its parent', async () => {
  const env = modalEnvironment()
  const trigger = env.element()
  trigger.focus()
  const parent = env.create()
  const child = env.create()
  parent.attach()
  child.attach()
  await Promise.all([child.mount(), parent.mount()])
  assert.equal(env.document.activeElement, child.sheet)
  assert.equal(parent.sheet.inert, true)
  const escape = keyEvent('Escape')
  env.dispatch(escape)
  assert.deepEqual(child.events, [['close']])
  assert.deepEqual(parent.events, [])
  child.unmount()
  assert.equal(env.document.activeElement, parent.sheet)
  parent.unmount()
  assert.equal(env.document.activeElement, trigger)
  assert.equal(env.document.body.style.overflow, 'auto')
})

test('removing the parent first does not unlock background scrolling while a child is still open', async () => {
  const env = modalEnvironment('clip')
  const parent = env.create()
  parent.attach()
  await parent.mount()
  parent.sheet.controls[0].focus()
  const child = env.create()
  child.attach()
  await child.mount()
  parent.unmount()
  assert.equal(env.document.body.style.overflow, 'hidden')
  assert.equal(env.document.activeElement, child.sheet)
  assert.equal(child.sheet.inert, false)
  assert.equal(env.listeners.size, 1)
  child.unmount()
  assert.equal(env.document.body.style.overflow, 'clip')
  assert.equal(env.listeners.size, 0)
})

test('modal focus wraps backward, recovers from outside focus, and handles an empty focus list', async () => {
  const env = modalEnvironment()
  const modal = env.create()
  modal.attach()
  await modal.mount()
  modal.sheet.controls[0].focus()
  env.dispatch(keyEvent('Tab', { shiftKey: true }))
  assert.equal(env.document.activeElement, modal.sheet.controls[1])
  env.element().focus()
  env.dispatch(keyEvent('Tab'))
  assert.equal(env.document.activeElement, modal.sheet.controls[0])
  modal.sheet.controls = [env.element(modal.sheet, false)]
  env.dispatch(keyEvent('Tab'))
  assert.equal(env.document.activeElement, modal.sheet)
  modal.exposed.resetScroll()
  assert.equal(modal.body.scrollTop, 0)
  modal.unmount()
})
