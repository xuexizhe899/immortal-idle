import { readFile } from 'node:fs/promises'
import ts from 'typescript'
import { createPinia, setActivePinia } from 'pinia'

function asModule(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
}

async function compile(relativePath, imports = {}) {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8')
  let output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  }).outputText
  for (const [specifier, destination] of Object.entries(imports)) {
    output = output.replaceAll(`from '${specifier}'`, `from ${JSON.stringify(destination)}`)
      .replaceAll(`from "${specifier}"`, `from ${JSON.stringify(destination)}`)
  }
  return asModule(output)
}

// Load production code without a bundler or generated test implementation. Both
// imports resolve to the same Vue/Pinia modules used by this test harness.
const clientUrl = await compile('../src/api/client.ts')
const storeUrl = await compile('../src/stores/game.ts', {
  pinia: import.meta.resolve('pinia'),
  vue: import.meta.resolve('vue'),
  '../api/client': clientUrl,
})
const { useGameStore } = await import(storeUrl)

export const preferencesKey = 'immortal-idle.preferences.v1'

export function disciple(id, extra = {}) {
  return { id, template_id: id, level: 1, exp: 0, realm: 1, stats: {}, bonuses: {}, equipment: [], pill_uses: {}, injury_stacks: 0, injured_until: null, busy: false, ...extra }
}

export function snapshot({ disciples = [disciple('alpha')], revision = 1, stamina = 3, activeRun = null, duty = [], inventory = { ling_cao: 5 }, bonuses = {}, reputation = 500 } = {}) {
  return {
    revision,
    status: activeRun ? (activeRun.affix_pending ? 'choosing_affix' : 'choosing_node') : 'idle',
    production: { cultivation: 10, spirit_stone: 5, stamina: .5, materials: {}, injury_recovery_multiplier: 1 },
    state: {
      schema_version: 1,
      resources: { cultivation: 100, spirit_stone: 100, stamina, reputation },
      disciples, duty_slots: duty.map(id => ({ disciple_id: id, assigned_at: '2026-11-11T00:00:00Z' })),
      duty_events: [], inventory, bonuses, unlocks: disciples.map(d => d.template_id),
      tower_floor: 0, active_run: activeRun, rng_seed: 1, logs: [],
    },
  }
}

export function activeRun(party = ['alpha'], extra = {}) {
  return {
    run_seed: 1234, rng_cursor: 0, mode: 'tower', party, hp: 600, max_hp: 600,
    nodes: [], choices: [{ kind: 'battle', enemy: 'battle_0', power: 20, reward: { cultivation: 10 } }],
    affix_options: [], affix_pending: false, affixes: [], pending_loot: {},
    started_at: '2026-11-11T00:00:00Z', last_battle: null, ...extra,
  }
}

function metadata(id) {
  return { slot_id: id, name: `宗门 ${id}`, revision: 1, schema_version: 1, updated_at: '2026-11-11T00:00:00Z', last_settled_at: '2026-11-11T00:00:00Z' }
}

export function harness(slots = { 1: snapshot() }, preferences = {}) {
  const saved = new Map(Object.entries(slots).map(([id, value]) => [Number(id), structuredClone(value)]))
  const storage = new Map([[preferencesKey, JSON.stringify(preferences)]])
  const handlers = new Map()
  const calls = []
  const oldFetch = globalThis.fetch
  const oldWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  const oldStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { setTimeout, clearTimeout } })
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => { storage.set(key, String(value)) },
    removeItem: key => { storage.delete(key) },
  } })
  globalThis.fetch = async (url, init = {}) => {
    const path = String(url).replace(/^\/api/, '')
    const method = init.method ?? 'GET'
    const request = { method, path, body: init.body ? JSON.parse(init.body) : undefined }
    calls.push(request)
    const handler = handlers.get(`${method} ${path}`)
    if (handler) return await handler(request)
    if (method === 'GET' && path === '/catalog') return json({
      rules: { max_party: 6, max_duty: 6 },
      disciples: { alpha: { name: '甲弟子' }, beta: { name: '乙弟子' }, gamma: { name: '丙弟子' } },
      recipes: { ju_qi_dan: { name: '聚气丹', kind: 'pill' } },
      weapons: {},
    })
    if (method === 'GET' && path === '/saves') return json([...saved.keys()].map(metadata))
    const weapons = /^\/saves\/(\d+)\/weapons$/.exec(path)
    if (method === 'GET' && weapons) {
      const content = saved.get(Number(weapons[1]))
      if (!content) return json({ detail: '存档不存在' }, 404)
      return json({ revision: content.revision, weapons: [] })
    }
    const match = /^\/saves\/(\d+)(\/settle)?$/.exec(path)
    if (match) {
      const content = saved.get(Number(match[1]))
      if (!content) return json({ detail: '存档不存在' }, 404)
      if (method === 'GET' && !match[2]) return json(content)
      if (method === 'POST' && match[2]) return json({ ...content, elapsed_hours: 0, dropped_hours: 0, gained: { cultivation: 0, spirit_stone: 0, stamina: 0, materials: {} }, warnings: [] })
    }
    throw new Error(`Unexpected request: ${method} ${path}`)
  }
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useGameStore()
  return {
    store, saved, calls,
    respond(method, path, handler) { handlers.set(`${method} ${path}`, handler) },
    count(method, path) { return calls.filter(call => call.method === method && call.path === path).length },
    preferences() { return JSON.parse(storage.get(preferencesKey)) },
    cleanup() {
      store.$dispose()
      setActivePinia(undefined)
      globalThis.fetch = oldFetch
      if (oldWindow) Object.defineProperty(globalThis, 'window', oldWindow)
      else delete globalThis.window
      if (oldStorage) Object.defineProperty(globalThis, 'localStorage', oldStorage)
      else delete globalThis.localStorage
    },
  }
}

export function json(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

export function deferred() {
  let resolve
  const promise = new Promise(accept => { resolve = accept })
  return { promise, resolve }
}
