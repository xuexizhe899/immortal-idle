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

test('a committed craft with a lost response does not spend materials or apply its permanent bonus twice', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST', '/saves/1/craft', request => {
    assert.deepEqual(request.body, { recipe_id: 'ju_qi_dan', target: null, revision: 1 })
    session.saved.set(1, snapshot({ revision: 2, inventory: { ling_cao: 3 }, bonuses: { cultivation_rate: .08 } }))
    throw new TypeError('Response lost')
  })

  await session.store.craft('ju_qi_dan', null)

  assert.equal(session.count('POST', '/saves/1/craft'), 1)
  assert.equal(session.count('GET', '/saves/1'), 1)
  assert.equal(session.store.state.inventory.ling_cao, 3)
  assert.equal(session.store.state.bonuses.cultivation_rate, .08)
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

  const first = session.store.craft('ju_qi_dan', null)
  assert.equal(session.store.busy, true)
  await session.store.craft('ju_qi_dan', null)
  await session.store.recruit('beta')
  assert.equal(session.count('POST', '/saves/1/craft'), 1)
  assert.equal(session.count('POST', '/saves/1/recruit'), 0)
  reply.resolve(json({ ...snapshot({ revision: 2, inventory: { ling_cao: 3 } }), bonuses: {}, inventory: { ling_cao: 3 } }))
  await first

  assert.equal(session.store.busy, false)
  assert.equal(session.store.state.inventory.ling_cao, 3)
})

test('switching saves restores each saved party and removes duplicate, missing, and duty members', async t => {
  const session = harness({
    1: snapshot({ disciples: [disciple('alpha'), disciple('duty')], duty: ['duty'] }),
    2: snapshot({ disciples: [disciple('beta'), disciple('gamma')] }),
  }, { slotId: 1, parties: { 1: ['alpha', 'alpha', 'missing', 'duty'], 2: ['beta'] } })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  assert.deepEqual([...session.store.party], ['alpha'])

  await session.store.switchSave(2)
  assert.deepEqual([...session.store.party], ['beta'])
  session.store.toggleParty('gamma')
  await session.store.switchSave(1)
  assert.deepEqual([...session.store.party], ['alpha'])
  await session.store.switchSave(2)

  assert.deepEqual([...session.store.party], ['beta', 'gamma'])
  assert.deepEqual(session.preferences().parties, { 1: ['alpha'], 2: ['beta', 'gamma'] })
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
