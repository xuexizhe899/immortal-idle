import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import ts from 'typescript'
import { harness, json, snapshot } from './store-harness.mjs'

const helperSource = await readFile(new URL('../src/presentation/materialSources.ts', import.meta.url), 'utf8')
const helperOutput = ts.transpileModule(helperSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { materialSources } = await import(`data:text/javascript;base64,${Buffer.from(helperOutput).toString('base64')}`)

// Execute the real setup script with Vue reactivity; no browser or copied navigation logic.
async function setupView(file, names, store, emit = () => {}) {
  const source = await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
  const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
  const output = ts.transpileModule(script, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const setup = new Function('computed', 'ref', 'watch', 'useGameStore', 'defineEmits', 'materialSources', 'resourceName', `${output}\nreturn { ${names.join(', ')} }`)
  const scope = effectScope()
  const values = scope.run(() => setup(computed, ref, watch, () => store, () => emit, materialSources, id => id))
  return { ...values, stop: () => scope.stop() }
}

function sect(id, regionId = 1, extra = {}) {
  return { id, region_id: regionId, area: 1, name: '云岚剑宗', style: '剑修', level: 1, material_id: 'chi_tong', special_material_id: 'gong_fa_qi_pei', conquered: true, loot: { chi_tong: 8 }, garrison: [], ...extra }
}
function node(item, extra = {}) {
  return { id: `node:${item.id}`, kind: 'sect', name: item.name, sect_id: item.id, region_id: item.region_id, locked: false, reason: '', retrial_rewards: { chi_tong: item.region_id === 2 ? 17 : 4 }, ...extra }
}
function map(current = 1, sects = [sect('sect_1'), sect('r2:sect_1', 2)]) {
  return { current_region: current, regions: [1, 2, 3].map(id => ({
    id, name: `地区${id}`, selected: id === current, unlocked: id !== 3,
    areas: [{ id: 1, unlocked: id !== 3 }],
    nodes: [...sects.filter(item => item.region_id === id).map(item => node(item)), { id: `r${id}:dungeon`, kind: 'dungeon', locked: id === 3 }],
    tower_rewards: { battle: { chi_tong: id === 2 ? 19 : 1 } },
  })) }
}
const catalog = {
  materials: { chi_tong: '赤铜', gong_fa_qi_pei: '攻伐器胚' },
  production: { materials: { chi_tong: 0, gong_fa_qi_pei: 0 } },
  disciples: {}, mode: { rewards: { battle: { chi_tong: 1 } } },
  sect_styles: [{ name: '剑修', retrial_reward: { chi_tong: 4 } }],
}
function state(sects, current = 1) {
  return { sects, facility_levels: { training: 1 }, world: { current_region: current, unlocked_regions: [1, 2], unlocked_areas: { 1: 1, 2: 1 } } }
}
function viewStore(current = 1, target = '') {
  const sects = [sect('sect_1'), sect('r2:sect_1', 2)]
  return reactive({ state: state(sects, current), slotId: 1, revision: 1, targetSectId: target, worldMap: map(current, sects), loadWorld: async () => {}, party: [], disciples: [], catalog })
}

test('a material target opens the exact same-name sect in the current map and stays closed after manual dismissal', async t => {
  const store = viewStore(2, 'r2:sect_1')
  const view = await setupView('views/WorldPanel.vue', ['selected', 'showingSect', 'choose'], store)
  t.after(view.stop)
  assert.equal(view.selected.value.sect_id, 'r2:sect_1')
  assert.equal(view.showingSect.value, true)
  view.showingSect.value = false
  store.worldMap = structuredClone(map(2))
  await nextTick()
  assert.equal(view.showingSect.value, false, 'a refreshed map must not reopen a dismissed sheet')
  view.choose(store.worldMap.regions[1].nodes.find(item => item.kind === 'dungeon'))
  await nextTick()
  assert.equal(store.targetSectId, '')
  assert.equal(view.selected.value.kind, 'dungeon')
})

test('a cross-region material target remains explicit until a successful region change', async t => {
  const store = viewStore(1, 'sect_1')
  const view = await setupView('views/WorldPanel.vue', ['selected', 'showingSect', 'targetElsewhere'], store)
  t.after(view.stop)
  assert.equal(view.showingSect.value, true)
  store.targetSectId = 'r2:sect_1'
  await nextTick()
  assert.equal(view.showingSect.value, false)
  assert.equal(view.targetElsewhere.value.node.sect_id, 'r2:sect_1')
  assert.notEqual(view.selected.value.sect_id, 'r2:sect_1')
  store.worldMap = map(2)
  store.state.world.current_region = 2
  await nextTick()
  assert.equal(view.targetElsewhere.value, null)
  assert.equal(view.selected.value.sect_id, 'r2:sect_1')
  assert.equal(view.showingSect.value, true)
})

test('a specific material source opens that sect instead of selecting another source', async t => {
  const store = viewStore()
  store.productionTarget = ''
  store.planProduction = () => { throw new Error('must not reselect the source') }
  const events = []
  const view = await setupView('components/game/MaterialSources.vue', ['go'], store, (...args) => events.push(args))
  t.after(view.stop)
  view.go('chi_tong', { panel: 'expedition', sectId: 'r2:sect_1' })
  assert.equal(store.targetSectId, 'r2:sect_1')
  assert.equal(store.productionTarget, 'chi_tong')
  assert.deepEqual(events, [['open', 'expedition']])
})

test('sect details use the exact server reward preview and never the catalog base value', async t => {
  const store = viewStore(2, 'r2:sect_1')
  const view = await setupView('views/ExpeditionPanel.vue', ['retrialReward'], store)
  t.after(view.stop)
  assert.deepEqual({ ...view.retrialReward.value }, { chi_tong: 17 })
  store.worldMap = null
  assert.deepEqual({ ...view.retrialReward.value }, {})
})

test('material sources distinguish region, area access and server-scaled rewards', () => {
  const sects = [sect('sect_1'), sect('r2:sect_1', 2), sect('r2:sect_4', 2, { area: 2, conquered: false }), sect('r3:sect_1', 3)]
  const matrix = materialSources(catalog, state(sects, 2), map(2, sects))
  const retrial = matrix.chi_tong.find(source => source.kind === 'retrial' && source.sectId === 'r2:sect_1')
  assert.match(retrial.detail, /地区2.*胜利 \+17/)
  assert.equal(retrial.available, true)
  assert.match(matrix.chi_tong.find(source => source.kind === 'tower').detail, /普通 \+19/)
  assert.match(matrix.chi_tong.find(source => source.kind === 'retrial' && source.sectId === 'sect_1').detail, /需先切换图层/)
  const area = matrix.chi_tong.find(source => source.kind === 'conquest' && source.sectId === 'r2:sect_4')
  assert.equal(area.available, false)
  assert.equal(area.blockedReason, '片区未开放')
  const locked = matrix.chi_tong.find(source => source.kind === 'garrison' && source.sectId === 'r3:sect_1')
  assert.equal(locked.available, false)
  assert.equal(locked.blockedReason, '地区未开放')
  assert.equal(locked.rate, undefined)
  const unloaded = materialSources(catalog, state(sects, 2))
  assert.match(unloaded.chi_tong.find(source => source.kind === 'tower').detail, /载入/)
  assert.match(unloaded.chi_tong.find(source => source.kind === 'retrial').detail, /载入/)
  assert.ok(!unloaded.chi_tong.some(source => /胜利 \+4|普通 \+1/.test(source.detail)))
})

test('production planning prefers reachable local sources and never travels automatically', async t => {
  const initial = snapshot()
  initial.state = { ...initial.state, ...state([sect('sect_1'), sect('r2:sect_4', 2, { area: 2 }), sect('r2:sect_1', 2, { conquered: false })], 2) }
  const session = harness({ 1: initial })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.catalog.production = catalog.production
  assert.equal(session.store.planProduction('gong_fa_qi_pei'), 'expedition')
  assert.equal(session.store.targetSectId, 'r2:sect_1')
  assert.equal(session.count('POST', '/saves/1/world/travel'), 0)
  assert.equal(session.store.planProduction('unknown_material'), 'expedition', 'an absent production key must not become duty income')
})

test('explicit region travel preserves its requested sect only after a successful response', async t => {
  const initial = snapshot()
  initial.state = { ...initial.state, ...state([sect('r2:sect_1', 2)]) }
  const session = harness({ 1: initial })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.catalog.production = catalog.production
  session.store.worldMap = map()
  session.store.planProduction('gong_fa_qi_pei')
  assert.equal(session.store.targetSectId, 'r2:sect_1')
  assert.match(session.store.notice, /切换至地区2/)
  assert.equal(session.count('POST', '/saves/1/world/travel'), 0)
  session.respond('POST', '/saves/1/world/travel', request => {
    assert.deepEqual(request.body, { revision: 1, region_id: 2 })
    const result = structuredClone(initial)
    result.revision = 2
    result.state.world.current_region = 2
    return json({ ...result, world: map(2) })
  })
  await session.store.travelRegion(2, 'r2:sect_1')
  assert.equal(session.store.targetSectId, 'r2:sect_1')
  assert.equal(session.store.worldMap.current_region, 2)
  session.store.targetSectId = 'sect_1'
  session.respond('POST', '/saves/1/world/travel', () => json({ detail: '此地区尚未开放' }, 400))
  await session.store.travelRegion(3, 'r3:sect_1')
  assert.equal(session.store.targetSectId, 'sect_1')
  assert.match(session.store.error, /此地区尚未开放/)
})
