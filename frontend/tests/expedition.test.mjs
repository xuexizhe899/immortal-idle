import assert from 'node:assert/strict'
import test from 'node:test'

import { activeRun, disciple, harness, json, snapshot } from './store-harness.mjs'

test('remote dock departure sends the explicit expedition mode and mirrors its active run', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.toggleParty('alpha')
  session.respond('POST', '/saves/1/run/start', request => {
    assert.deepEqual(request.body, { party: ['alpha'], revision: 1, mode: 'expedition' })
    return json(snapshot({
      revision: 2,
      stamina: 1,
      disciples: [disciple('alpha', { busy: true })],
      activeRun: activeRun(['alpha'], { mode: 'expedition' }),
    }))
  })

  await session.store.startRun(['alpha'], 'expedition')

  assert.equal(session.store.run.run.mode, 'expedition')
  assert.equal(session.store.resources.stamina, 1)
  assert.equal(session.store.busy, false)
})

test('a lost settlement response restores its review without settling twice or leaking across saves', async t => {
  const initial = snapshot({ revision: 4, activeRun: activeRun(['alpha'], { mode: 'expedition', hp: 0 }) })
  initial.status = 'defeated'
  const session = harness({ 1: initial, 2: snapshot() })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const review = {
    mode: 'expedition', cleared: 1, total_nodes: 12, victory: false,
    end_reason: 'defeated', loot: { cultivation: 4, reputation: 1 }, last_battle: null,
  }
  const settled = snapshot({ revision: 5 })
  settled.state.last_run_review = review
  settled.state.resources.cultivation = 104
  session.respond('POST', '/saves/1/run/settle', request => {
    assert.deepEqual(request.body, { revision: 4 })
    session.saved.set(1, settled)
    throw new TypeError('Response lost after commit')
  })

  await session.store.settleRun()

  assert.equal(session.count('POST', '/saves/1/run/settle'), 1)
  assert.equal(session.store.state.active_run, null)
  assert.deepEqual(session.store.state.last_run_review, review)
  assert.equal(session.store.resources.cultivation, 104)
  await session.store.switchSave(2)
  assert.equal(session.store.state.last_run_review, undefined)
  await session.store.switchSave(1)
  assert.deepEqual(session.store.state.last_run_review, review)
  assert.equal(session.store.resources.cultivation, 104)
  assert.equal(session.count('POST', '/saves/1/run/settle'), 1)
})
