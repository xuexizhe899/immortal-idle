import assert from 'node:assert/strict'
import test from 'node:test'
import { activeRun, deferred, disciple, harness, json, snapshot } from './store-harness.mjs'

test('an accepted departure with a lost response consumes stamina once and synchronizes the active expedition', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.toggleParty('alpha')
  session.respond('POST', '/saves/1/run/start', request => {
    assert.deepEqual(request.body, { party: ['alpha'], revision: 1 })
    session.saved.set(1, snapshot({ revision: 2, stamina: 2, disciples: [disciple('alpha', { busy: true })], activeRun: activeRun() }))
    throw new TypeError('Connection closed after the command was committed')
  })

  await session.store.startRun(['alpha'])

  assert.equal(session.count('POST', '/saves/1/run/start'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.resources.stamina, 2)
  assert.equal(session.store.revision, 2)
  assert.equal(session.store.status, 'choosing_node')
  assert.deepEqual([...session.store.run.run.party], ['alpha'])
  assert.equal(session.store.busy, false)
  assert.equal(session.store.operation, '')
  assert.match(session.store.error, /确认最新进度/)
})

test('a committed craft with a lost response does not spend materials or store the pill twice', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/craft', request => {
    assert.deepEqual(request.body, { recipe_id: 'ju_qi_dan', revision: 1, quantity: 1, grade: 1 })
    session.saved.set(1, snapshot({ revision: 2, inventory: { ling_cao: 3, ju_qi_dan: 1 } }))
    throw new TypeError('Response lost')
  })

  await session.store.craft('ju_qi_dan')

  assert.equal(session.count('POST', '/saves/1/craft'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.state.inventory.ling_cao, 3)
  assert.equal(session.store.state.inventory.ju_qi_dan, 1)
  assert.equal(session.store.notice, null, 'an unconfirmed response must not produce a second success message')
  assert.equal(session.store.busy, false)
})

test('a stale battle choice synchronizes a 409 response without replaying the choice against the new node', async t => {
  const session = harness({ 1: snapshot({ activeRun: activeRun() }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const latestBattle = { id: 'battle-once', party_power: 80, enemy_power: 20, hp_before: 600, hp_after: 585, damage: 15, won: true, loot: { cultivation: 10 }, node: { kind: 'battle', enemy: 'battle_0', power: 20, reward: { cultivation: 10 } } }
  session.respond('POST', '/saves/1/run/choose', request => {
    assert.deepEqual(request.body, { choice: 0, revision: 1 })
    session.saved.set(1, snapshot({ revision: 2, activeRun: activeRun(['alpha'], {
      hp: 585, nodes: [latestBattle.node], choices: [], affix_pending: true,
      affix_options: ['po_jun', 'lie_jia', 'xue_yong'], pending_loot: { cultivation: 10 }, last_battle: latestBattle,
    }) }))
    return json({ detail: '存档已更新' }, 409)
  })

  await session.store.choose(0)

  assert.equal(session.count('POST', '/saves/1/run/choose'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.status, 'choosing_affix')
  assert.equal(session.store.run.run.nodes.length, 1)
  assert.equal(session.store.battleResult.id, 'battle-once')
  assert.equal(session.store.run.run.hp, 585)
  assert.match(session.store.error, /进度已有更新/)
  assert.equal(session.store.busy, false)
})

test('a second consuming command is ignored while the first request is pending', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const reply = deferred()
  session.respond('POST', '/saves/1/craft', () => reply.promise)

  const first = session.store.craft('ju_qi_dan')
  assert.equal(session.store.busy, true)
  await session.store.craft('ju_qi_dan')
  await session.store.recruit('beta')
  assert.equal(session.count('POST', '/saves/1/craft'), 1)
  assert.equal(session.count('POST', '/saves/1/recruit'), 0)
  reply.resolve(json({ ...snapshot({ revision: 2, inventory: { ling_cao: 3, ju_qi_dan: 1 } }), bonuses: {}, inventory: { ling_cao: 3, ju_qi_dan: 1 } }))
  await first

  assert.equal(session.store.busy, false)
  assert.equal(session.store.state.inventory.ju_qi_dan, 1)
})

test('switching saves preserves duty members and removes duplicate and missing party members', async t => {
  const session = harness({
    1: snapshot({ disciples: [disciple('alpha'), disciple('duty')], duty: ['duty'] }),
    2: snapshot({ disciples: [disciple('beta'), disciple('gamma')] }),
  }, { slotId: 1, parties: { 1: ['alpha', 'alpha', 'missing', 'duty'], 2: ['beta'] } })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  assert.deepEqual([...session.store.party], ['alpha', 'duty'])

  await session.store.switchSave(2)
  assert.deepEqual([...session.store.party], ['beta'])
  session.store.toggleParty('gamma')
  await session.store.switchSave(1)
  assert.deepEqual([...session.store.party], ['alpha', 'duty'])
  await session.store.switchSave(2)

  assert.deepEqual([...session.store.party], ['beta', 'gamma'])
  assert.deepEqual(session.preferences().parties, { 1: ['alpha', 'duty'], 2: ['beta', 'gamma'] })
  assert.equal(session.store.slotId, 2)
})

test('an interrupted expedition restores the server party instead of a local draft', async t => {
  const session = harness({ 1: snapshot({
    disciples: [disciple('alpha'), disciple('beta', { busy: true })],
    activeRun: activeRun(['beta'], { hp: 410, affix_pending: true, affix_options: ['po_jun'], nodes: [{ kind: 'battle', enemy: 'battle_0', power: 20, reward: {} }] }),
  }) }, { slotId: 1, parties: { 1: ['alpha'] } })
  t.after(() => session.cleanup())

  await session.store.bootstrap()

  assert.equal(session.store.status, 'choosing_affix')
  assert.deepEqual([...session.store.party], ['beta'])
  assert.equal(session.store.run.run.hp, 410)
  assert.deepEqual([...session.store.run.run.affix_options], ['po_jun'])
  assert.equal(session.count('POST', '/saves/1/run/start'), 0)
})

test('deleting the current save with a lost response recovers an existing save without repeating deletion or creating another', async t => {
  const session = harness({
    1: snapshot(),
    2: snapshot({ revision: 7, disciples: [disciple('beta')], stamina: 9 }),
  }, { slotId: 1, parties: { 2: ['beta'] } })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('DELETE', '/saves/1', () => {
    session.saved.delete(1)
    throw new TypeError('Deletion committed, response lost')
  })

  await session.store.deleteSave(1)

  assert.equal(session.count('DELETE', '/saves/1'), 1)
  assert.equal(session.count('GET', '/saves/1'), 0, 'do not attempt to read a save already absent from the listing')
  assert.equal(session.count('POST', '/saves'), 0, 'an existing save must be reused')
  assert.equal(session.count('POST', '/saves/2/settle'), 1)
  assert.equal(session.store.slotId, 2)
  assert.equal(session.store.revision, 7)
  assert.equal(session.store.resources.stamina, 9)
  assert.deepEqual([...session.store.party], ['beta'])
  assert.deepEqual(session.store.saves.map(save => save.slot_id), [2])
  assert.equal(session.store.busy, false)
  assert.match(session.store.error, /确认最新进度/)
})

test('using a pill applies the server snapshot and refreshes that disciple training', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const preview = {
    disciple_id: 'alpha', level: 1, realm: 1, level_cap: 3, max_realm: 3,
    legacy_over_cap: false,
    current: { level: 1, realm: 1, health: 100, attack: 11, defense: 5, speed: 10, duty_rates: {} },
    next_level: null, next_realm: null,
  }
  session.respond('GET', '/saves/1/disciples/alpha/training', () => json(preview))
  session.respond('POST', '/saves/1/items/use', request => {
    assert.deepEqual(request.body, { item_id: 'ju_qi_dan', target: 'alpha', revision: 1 })
    return json({
      ...snapshot({ revision: 2, inventory: { ling_cao: 5 }, disciples: [disciple('alpha', { bonuses: { atk: .05 } })] }),
      disciple: disciple('alpha', { bonuses: { atk: .05 } }),
      item_id: 'ju_qi_dan',
    })
  })

  await session.store.usePill('ju_qi_dan', 'alpha')

  assert.equal(session.count('POST', '/saves/1/items/use'), 1)
  assert.equal(session.count('GET', '/saves/1/disciples/alpha/training'), 1)
  assert.equal(session.store.state.disciples[0].bonuses.atk, .05)
  assert.equal(session.store.notice, '甲弟子已服用聚气丹。')
  assert.equal(session.store.training?.disciple_id, 'alpha')
})

test('equipping a weapon uses the server weapon list and preserves a lost-response sync', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const weapon = {
    id: 'w1', name: '青龙偃月刀', template_id: 'alpha', template_name: '甲弟子',
    stats: { atk: .1, damage: .05 }, inputs: { han_tie: 1 },
    unlock_floor: 8, unlock_level: 3, owned: true, in_inventory: false,
    equipped_by: 'alpha', reason: '', craftable: false,
  }
  const preview = {
    disciple_id: 'alpha', level: 3, realm: 1, level_cap: 3, max_realm: 3,
    legacy_over_cap: false,
    current: { level: 3, realm: 1, health: 120, attack: 20, defense: 7, speed: 10, duty_rates: {} },
    next_level: null, next_realm: null,
  }
  session.respond('GET', '/saves/1/disciples/alpha/training', () => json(preview))
  session.respond('POST', '/saves/1/weapons/equip', request => {
    assert.deepEqual(request.body, { weapon_id: 'w1', disciple_id: 'alpha', revision: 1 })
    session.saved.set(1, snapshot({ revision: 2, disciples: [disciple('alpha', { equipment: ['w1'] })] }))
    return json({ ...session.saved.get(1), weapons: [weapon] })
  })

  await session.store.equipWeapon('w1', 'alpha')

  assert.equal(session.count('POST', '/saves/1/weapons/equip'), 1)
  assert.equal(session.count('GET', '/saves/1/disciples/alpha/training'), 1)
  assert.deepEqual([...session.store.state.disciples[0].equipment], ['w1'])
  assert.equal(session.store.weapons[0].equipped_by, 'alpha')
  assert.equal(session.store.notice, '青龙偃月刀已装备。')
})

test('repeating the same notice registers a fresh feedback event so it can appear again', async t => {
  const ids = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta']
  const session = harness({ 1: snapshot({ disciples: ids.map(id => disciple(id)) }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  for (const id of ids.slice(0, 6)) session.store.toggleParty(id)
  assert.equal(session.store.party.length, 6)

  session.store.toggleParty('eta')
  const firstEvent = session.store.noticeId
  assert.equal(session.store.notice, '队伍已满，请先移除一名弟子。')
  assert.ok(firstEvent > 0)

  session.store.toggleParty('eta')
  assert.equal(session.store.notice, '队伍已满，请先移除一名弟子。')
  assert.equal(session.store.noticeId, firstEvent + 1, 'identical text must still count as a new notice')

  session.store.dismissNotice()
  assert.equal(session.store.notice, null)
  session.store.toggleParty('eta')
  assert.equal(session.store.noticeId, firstEvent + 2)
})


test('six-person formation retains explicit position order across save switching and departure', async t => {
  const ids = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta']
  const session = harness({
    1: snapshot({ disciples: ids.map(id => disciple(id)) }),
    2: snapshot({ disciples: [disciple('other')] }),
  })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  for (const id of ids) session.store.toggleParty(id)
  assert.deepEqual([...session.store.party], ids.slice(0, 6))
  assert.match(session.store.notice, /队伍已满/)
  session.store.moveParty('zeta', -1)
  session.store.moveParty('alpha', -1)
  const ordered = ['alpha', 'beta', 'gamma', 'delta', 'zeta', 'epsilon']
  assert.deepEqual([...session.store.party], ordered)
  await session.store.switchSave(2)
  await session.store.switchSave(1)
  assert.deepEqual([...session.store.party], ordered, 'snapshot refresh must preserve formation rather than roster order')
  session.respond('POST', '/saves/1/run/start', request => {
    assert.deepEqual(request.body.party, ordered)
    return json(snapshot({ revision: 2, disciples: ids.map(id => disciple(id, { busy: ordered.includes(id) })), activeRun: activeRun(ordered) }))
  })
  await session.store.startRun([...session.store.party])
  session.store.moveParty('alpha', 1)
  assert.deepEqual([...session.store.party], ordered, 'an active expedition locks positions')
  assert.equal(session.count('POST', '/saves/1/run/start'), 1)
})

test('a training preview loads and a breakthrough refreshes state and preview', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const preview = {
    disciple_id: 'alpha', level: 1, realm: 1, level_cap: 3, max_realm: 3,
    legacy_over_cap: false,
    current: { level: 1, realm: 1, health: 100, attack: 10, defense: 5, speed: 10, duty_rates: {} },
    next_level: null, next_realm: null,
  }
  session.respond('GET', '/saves/1/disciples/alpha/training', () => json(preview))
  await session.store.loadTraining('alpha')
  assert.equal(session.store.training?.disciple_id, 'alpha')

  const advanced = { disciple: disciple('alpha', { level: 3, realm: 2 }), costs: { reputation: 110 } }
  session.saved.set(1, snapshot({ revision: 2, disciples: [advanced.disciple] }))
  session.respond('POST', '/saves/1/disciples/alpha/breakthrough', request => {
    assert.deepEqual(request.body, { revision: 1 })
    return json({ ...session.saved.get(1), ...advanced })
  })
  await session.store.breakthrough('alpha')

  assert.equal(session.store.state?.disciples[0].realm, 2)
  assert.equal(session.count('POST', '/saves/1/disciples/alpha/breakthrough'), 1)
  assert.equal(session.store.training?.disciple_id, 'alpha')
})

test('a committed breakthrough with a lost response synchronizes without replaying the command', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const advanced = { disciple: disciple('alpha', { level: 3, realm: 2 }), costs: { reputation: 110 } }
  session.respond('POST', '/saves/1/disciples/alpha/breakthrough', request => {
    assert.deepEqual(request.body, { revision: 1 })
    session.saved.set(1, snapshot({ revision: 2, disciples: [advanced.disciple] }))
    throw new TypeError('Response lost')
  })

  await session.store.breakthrough('alpha')

  assert.equal(session.count('POST', '/saves/1/disciples/alpha/breakthrough'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.state?.disciples[0].realm, 2)
  assert.match(session.store.error, /确认最新进度/)
  assert.equal(session.store.busy, false)
})

test('a delayed weapon list cannot overwrite a newer request from the same revision', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const earlier = deferred()
  session.respond('GET', '/saves/1/weapons', () => earlier.promise)
  const pending = session.store.loadWeapons()
  session.respond('GET', '/saves/1/weapons', () => json({ revision: 1, weapons: [{ id: 'newer' }] }))
  await session.store.loadWeapons()

  earlier.resolve(json({ revision: 1, weapons: [{ id: 'earlier' }] }))
  await pending

  assert.deepEqual(session.store.weapons.map(weapon => weapon.id), ['newer'])
})

test('a weapon response older than the current save revision is ignored', async t => {
  const session = harness({ 1: snapshot({ revision: 3 }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('GET', '/saves/1/weapons', () => json({ revision: 3, weapons: [{ id: 'current' }] }))
  await session.store.loadWeapons()
  session.respond('GET', '/saves/1/weapons', () => json({ revision: 2, weapons: [{ id: 'stale' }] }))

  await session.store.loadWeapons()

  assert.deepEqual(session.store.weapons.map(weapon => weapon.id), ['current'])
})

for (const lateFailure of [false, true]) {
  test(`a weapon read ${lateFailure ? 'failure' : 'response'} arriving after a successful craft preserves its result`, async t => {
    const session = harness()
    t.after(() => session.cleanup())
    await session.store.bootstrap()
    const earlier = deferred()
    session.respond('GET', '/saves/1/weapons', () => earlier.promise)
    const pending = session.store.loadWeapons()
    session.respond('POST', '/saves/1/weapons/craft', () => json({
      ...snapshot({ revision: 2 }), weapons: [{ id: 'crafted', name: '新铸专武', owned: true }],
    }))
    await session.store.craftWeapon('crafted')

    earlier.resolve(lateFailure
      ? json({ detail: '迟到的读取失败' }, 503)
      : json({ revision: 1, weapons: [] }))
    await pending

    assert.equal(session.store.revision, 2)
    assert.deepEqual(session.store.weapons.map(weapon => weapon.id), ['crafted'])
    assert.equal(session.store.error, null)
  })
}

test('an old weapon read failure does not clear a newer list or replace feedback', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const earlier = deferred()
  session.respond('GET', '/saves/1/weapons', () => earlier.promise)
  const pending = session.store.loadWeapons()
  session.respond('GET', '/saves/1/weapons', () => json({ revision: 1, weapons: [{ id: 'current' }] }))
  await session.store.loadWeapons()
  session.store.error = '当前操作提示'

  earlier.resolve(json({ detail: '迟到的读取失败' }, 503))
  await pending

  assert.deepEqual(session.store.weapons.map(weapon => weapon.id), ['current'])
  assert.equal(session.store.error, '当前操作提示')
})

test('returning to the same save does not reactivate its previous weapon request', async t => {
  const session = harness({ 1: snapshot(), 2: snapshot() })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const earlier = deferred()
  session.respond('GET', '/saves/1/weapons', () => earlier.promise)
  const pending = session.store.loadWeapons()
  await session.store.switchSave(2)
  session.respond('GET', '/saves/1/weapons', () => json({ revision: 1, weapons: [{ id: 'returned' }] }))
  await session.store.switchSave(1)

  earlier.resolve(json({ revision: 1, weapons: [{ id: 'previous-visit' }] }))
  await pending

  assert.deepEqual(session.store.weapons.map(weapon => weapon.id), ['returned'])
})
