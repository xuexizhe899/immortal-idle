import assert from 'node:assert/strict'
import test from 'node:test'
import { activeRun, deferred, disciple, harness, json, snapshot } from './store-harness.mjs'

function item(id = 'gear_1', extra = {}) {
  return { id, definition_id: 'qing_feng_blade', name: '青锋剑', slot: 'weapon', tier: 1, level: 0, main_stat: 'atk', main_value: .08, growth_per_level: .1, affix: 'spd', affix_grade: 1, affix_value: .02, extra_stats: {}, pending_affix: null, invested: {}, locked: false, source: 'drop', ...extra }
}
function game({ gear = [item()], region = 1, unlocked = [1], ...options } = {}) {
  const result = snapshot(options)
  result.state.gear = Object.fromEntries(gear.map(entry => [entry.id, entry]))
  result.state.world = { current_region: region, unlocked_regions: unlocked, unlocked_areas: { 1: 1 }, cleared_nodes: [], claimed_nodes: [], pending_invasions: { 1: 1 }, invasion_waves: { 1: 1 }, last_invasion_at: {}, tower_records: {} }
  return result
}
function gearList(content, items = Object.values(content.state.gear)) {
  return { revision: content.revision, items: items.map(entry => ({ ...entry, stats: { atk: .08, spd: .02 }, max_level: 3, upgrade_costs: { lian_qi_jing_cui: 2 }, upgrade_stats: { atk: .088, spd: .02 }, upgradeable: true, upgrade_reason: '', equipped_by: null, equip_reason: '', unequip_reason: '', reforge_costs: {}, reforge_reason: '', resolve_reason: '', smelt_returns: { lian_qi_jing_cui: 2 }, smelt_reason: '', lock_reason: '' })), slots: { weapon: '武器', armor: '盔甲', boots: '靴子', ring: '戒指' }, material: 'lian_qi_jing_cui', material_name: '炼器精粹' }
}
function worldView(content) {
  return { current_region: content.state.world.current_region, regions: [], invasions: { pending: 1, cap: 3, wave: 1, hours_per_wave: 4, next_at: null, critical_nodes: [] }, ascension: { target_region: 2, token_id: 'sheng_xian_ling', held: content.state.inventory.sheng_xian_ling ?? 0, can_ascend: false, reason: '' } }
}
function installReads(session) {
  for (const id of session.saved.keys()) {
    session.respond('GET', `/saves/${id}/equipment`, () => json(gearList(session.saved.get(id))))
    session.respond('GET', `/saves/${id}/world`, () => {
      const content = session.saved.get(id)
      return json({ ...content, world: worldView(content) })
    })
  }
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test('a committed equipment upgrade with a lost response spends once and restores the returned gear view', async t => {
  const session = harness({ 1: game({ inventory: { lian_qi_jing_cui: 6 } }) })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/equipment', request => {
    assert.deepEqual(request.body, { revision: 1, action: 'upgrade', item_id: 'gear_1' })
    session.saved.set(1, game({ revision: 2, inventory: { lian_qi_jing_cui: 4 }, gear: [item('gear_1', { level: 1, invested: { lian_qi_jing_cui: 2 } })] }))
    throw new TypeError('Upgrade committed, response lost')
  })
  await session.store.equipmentAction('upgrade', 'gear_1')
  await flush()
  assert.equal(session.count('POST', '/saves/1/equipment'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.count('GET', '/saves/1/equipment'), 1)
  assert.equal(session.store.state.inventory.lian_qi_jing_cui, 4)
  assert.equal(session.store.gearList[0].level, 1)
  assert.equal(session.store.revision, 2)
  assert.equal(session.store.notice, null)
  assert.equal(session.store.busy, false)
  assert.match(session.store.error, /确认最新进度/)
})

test('a committed smelt with a lost response removes the item once and recovers exact server materials', async t => {
  const session = harness({ 1: game({ inventory: { lian_qi_jing_cui: 4 } }) })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/equipment', request => {
    assert.equal(request.body.action, 'smelt')
    session.saved.set(1, game({ revision: 2, gear: [], inventory: { lian_qi_jing_cui: 9 } }))
    throw new TypeError('Smelt committed, response lost')
  })
  await session.store.equipmentAction('smelt', 'gear_1')
  await flush()
  assert.equal(session.count('POST', '/saves/1/equipment'), 1)
  assert.deepEqual(session.store.state.gear, {})
  assert.deepEqual(session.store.gearList, [])
  assert.equal(session.store.state.inventory.lian_qi_jing_cui, 9)
})

test('a committed map departure with a lost response consumes stamina once and retains its fixed run', async t => {
  const session = harness({ 1: game() })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  session.store.toggleParty('alpha')
  session.respond('POST', '/saves/1/world/start', request => {
    assert.deepEqual(request.body, { revision: 1, node_id: 'region_1_dungeon', party: ['alpha'], practice: false, tower_tier: 1 })
    session.saved.set(1, game({ revision: 2, stamina: 1, disciples: [disciple('alpha', { busy: true })], activeRun: activeRun(['alpha'], { mode: 'dungeon', world_node_id: 'region_1_dungeon', practice: false, pending_gear: [item('gear_2')] }) }))
    throw new TypeError('Departure committed, response lost')
  })
  await session.store.startWorld('region_1_dungeon')
  await flush()
  assert.equal(session.count('POST', '/saves/1/world/start'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.resources.stamina, 1)
  assert.equal(session.store.run.run.run_seed, 1234)
  assert.equal(session.store.run.run.world_node_id, 'region_1_dungeon')
  assert.equal(session.store.run.run.pending_gear[0].id, 'gear_2')
  assert.equal(session.store.state.gear.gear_2, undefined, 'pending loot must not be inserted into the permanent inventory by the client')
})

test('a committed ascension with a lost response consumes the token once and restores the new layer', async t => {
  const session = harness({ 1: game({ inventory: { sheng_xian_ling: 1 } }) })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/world/ascend', request => {
    assert.deepEqual(request.body, { revision: 1 })
    session.saved.set(1, game({ revision: 2, inventory: {}, region: 2, unlocked: [1, 2] }))
    throw new TypeError('Ascension committed, response lost')
  })
  await session.store.ascend()
  await flush()
  assert.equal(session.count('POST', '/saves/1/world/ascend'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.state.inventory.sheng_xian_ling, undefined)
  assert.deepEqual([...session.store.state.world.unlocked_regions], [1, 2])
  assert.equal(session.store.worldMap.current_region, 2)
  assert.equal(session.store.notice, null)
})

test('equipment commands preserve explicit disciple, lock and keep-old choices in their request', async t => {
  const session = harness({ 1: game() })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  const choices = [['equip', { disciple_id: 'alpha' }], ['lock', { locked: true }], ['lock', { locked: false }], ['resolve', { keep: true }], ['resolve', { keep: false }]]
  for (const [action, options] of choices) {
    const revision = session.store.revision
    session.respond('POST', '/saves/1/equipment', request => {
      assert.deepEqual(request.body, { revision, action, item_id: 'gear_1', ...options })
      const content = game({ revision: revision + 1 })
      session.saved.set(1, content)
      return json({ ...content, items: gearList(content).items, message: '装备已更新' })
    })
    await session.store.equipmentAction(action, 'gear_1', options)
  }
  assert.equal(session.count('POST', '/saves/1/equipment'), choices.length)
})

test('an earlier equipment preview cannot overwrite the command response at a newer revision', async t => {
  const session = harness({ 1: game() })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  const earlier = deferred()
  session.respond('GET', '/saves/1/equipment', () => earlier.promise)
  const pending = session.store.loadEquipment()
  const content = game({ revision: 2, gear: [item('gear_1', { level: 1 })] })
  session.respond('POST', '/saves/1/equipment', () => json({ ...content, items: gearList(content).items, message: '强化完成' }))
  await session.store.equipmentAction('upgrade', 'gear_1')
  earlier.resolve(json(gearList(game())))
  await pending
  assert.equal(session.store.revision, 2)
  assert.equal(session.store.gearList[0].level, 1)
  assert.equal(session.store.equipmentLoading, false)
  assert.equal(session.store.notice, '强化完成')
})

test('an earlier map preview cannot replace a newer travel result or its feedback', async t => {
  const session = harness({ 1: game({ unlocked: [1, 2] }) })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  const earlier = deferred()
  session.respond('GET', '/saves/1/world', () => earlier.promise)
  const pending = session.store.loadWorld()
  session.store.targetSectId = 'old-sect'
  const content = game({ revision: 2, region: 2, unlocked: [1, 2] })
  session.respond('POST', '/saves/1/world/travel', request => {
    assert.deepEqual(request.body, { revision: 1, region_id: 2 })
    return json({ ...content, world: worldView(content) })
  })
  await session.store.travelRegion(2)
  earlier.resolve(json({ ...game(), world: worldView(game()) }))
  await pending
  assert.equal(session.store.revision, 2)
  assert.equal(session.store.worldMap.current_region, 2)
  assert.equal(session.store.targetSectId, '')
  assert.equal(session.store.worldLoading, false)
  assert.match(session.store.notice, /已抵达所选地区/)
})

for (const revisit of [false, true]) {
  test(`equipment and world previews from a previous save visit remain isolated${revisit ? ' after returning to that save' : ''}`, async t => {
    const session = harness({ 1: game(), 2: game({ gear: [item('gear_other')], region: 2 }) })
    t.after(() => session.cleanup())
    installReads(session)
    await session.store.bootstrap()
    const oldGear = deferred(), oldWorld = deferred()
    session.respond('GET', '/saves/1/equipment', () => oldGear.promise)
    session.respond('GET', '/saves/1/world', () => oldWorld.promise)
    const gearPending = session.store.loadEquipment(), worldPending = session.store.loadWorld()
    await session.store.switchSave(2)
    assert.deepEqual(session.store.gearList, [])
    assert.equal(session.store.gearRules, null)
    assert.equal(session.store.worldMap, null)
    if (revisit) {
      installReads(session)
      await session.store.switchSave(1)
    }
    await Promise.all([session.store.loadEquipment(), session.store.loadWorld()])
    oldGear.resolve(json(gearList(game({ gear: [item('stale_gear')] }))))
    oldWorld.resolve(json({ ...game(), world: { ...worldView(game()), current_region: 99 } }))
    await Promise.all([gearPending, worldPending])
    assert.equal(session.store.slotId, revisit ? 1 : 2)
    assert.equal(session.store.gearList[0].id, revisit ? 'gear_1' : 'gear_other')
    assert.equal(session.store.worldMap.current_region, revisit ? 1 : 2)
    assert.equal(session.store.equipmentLoading, false)
    assert.equal(session.store.worldLoading, false)
  })
}

test('the command lock blocks duplicate equipment spending and concurrent ascension', async t => {
  const session = harness({ 1: game() })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  const reply = deferred()
  session.respond('POST', '/saves/1/equipment', () => reply.promise)
  const pending = session.store.equipmentAction('upgrade', 'gear_1')
  await session.store.equipmentAction('upgrade', 'gear_1')
  await session.store.ascend()
  assert.equal(session.count('POST', '/saves/1/equipment'), 1)
  assert.equal(session.count('POST', '/saves/1/world/ascend'), 0)
  const content = game({ revision: 2, gear: [item('gear_1', { level: 1 })] })
  reply.resolve(json({ ...content, items: gearList(content).items, message: '强化完成' }))
  await pending
  assert.equal(session.store.busy, false)
  assert.equal(session.store.gearList[0].level, 1)
})

test('equipment and map previews from before an unrelated resource mutation cannot enter the newer revision', async t => {
  const session = harness({ 1: game() })
  t.after(() => session.cleanup())
  installReads(session)
  await session.store.bootstrap()
  await Promise.all([session.store.loadEquipment(), session.store.loadWorld()])
  const oldGear = deferred(), oldWorld = deferred()
  session.respond('GET', '/saves/1/equipment', () => oldGear.promise)
  session.respond('GET', '/saves/1/world', () => oldWorld.promise)
  const gearPending = session.store.loadEquipment(), worldPending = session.store.loadWorld()
  session.respond('POST', '/saves/1/craft', () => json(game({ revision: 2, inventory: { ju_qi_dan: 1 } })))
  await session.store.craft('ju_qi_dan')
  oldGear.resolve(json(gearList(game({ gear: [item('stale_gear')] }))))
  oldWorld.resolve(json({ ...game(), world: { ...worldView(game()), current_region: 99 } }))
  await Promise.all([gearPending, worldPending])
  assert.equal(session.store.revision, 2)
  assert.equal(session.store.gearList[0].id, 'gear_1')
  assert.equal(session.store.worldMap.current_region, 1)
  assert.equal(session.store.state.inventory.ju_qi_dan, 1)
  assert.equal(session.store.error, null)
})

for (const [method, path] of [['loadEquipment', '/saves/1/equipment'], ['loadWorld', '/saves/1/world']]) {
  test(`a late silent ${method} failure does not erase the current command error`, async t => {
    const session = harness({ 1: game() })
    t.after(() => session.cleanup())
    installReads(session)
    await session.store.bootstrap()
    session.store.error = '上一次提示'
    const earlier = deferred()
    session.respond('GET', path, () => earlier.promise)
    const pending = session.store[method](true)
    session.respond('POST', '/saves/1/craft', () => json({ detail: '当前材料不足，无法炼制' }, 400))
    await session.store.craft('ju_qi_dan')
    earlier.resolve(json({ detail: '迟到的预览查询失败' }, 503))
    await pending
    assert.equal(session.store.error, '当前材料不足，无法炼制')
    assert.equal(session.store.revision, 1)
  })
}

for (const path of ['/saves/1/equipment', '/saves/1/world']) {
  test(`a failed background ${path} refresh preserves the lost-command recovery message`, async t => {
    const session = harness({ 1: game() })
    t.after(() => session.cleanup())
    installReads(session)
    await session.store.bootstrap()
    const background = deferred()
    session.respond('GET', path, () => background.promise)
    session.respond('POST', '/saves/1/equipment', () => {
      session.saved.set(1, game({ revision: 2, gear: [item('gear_1', { level: 1 })] }))
      throw new TypeError('Upgrade committed, response lost')
    })
    await session.store.equipmentAction('upgrade', 'gear_1')
    const recoveryMessage = session.store.error
    assert.match(recoveryMessage, /确认最新进度/)
    background.resolve(json({ detail: '背景查询暂不可用' }, 503))
    await flush()
    assert.equal(session.store.error, recoveryMessage)
    assert.equal(session.store.revision, 2)
    assert.equal(session.count('POST', '/saves/1/equipment'), 1)
    assert.equal(session.count('GET', '/saves/1'), 1)
  })
}
