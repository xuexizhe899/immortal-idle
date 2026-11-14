import assert from 'node:assert/strict'
import test from 'node:test'
import { activeRun, deferred, disciple, harness, json, snapshot } from './store-harness.mjs'

test('a duty disciple can be selected and departs in one command with the chosen sect', async t => {
  const session = harness({ 1:snapshot({ disciples:[disciple('alpha'),disciple('beta'),disciple('gamma')],duty:['alpha'] }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  for (const id of ['alpha','beta','gamma']) session.store.toggleParty(id)
  assert.deepEqual([...session.store.party],['alpha','beta','gamma'])
  session.respond('POST','/saves/1/run/start',request => {
    assert.deepEqual(request.body,{ party:['alpha','beta','gamma'],revision:1,mode:'expedition',sect_id:'sect_1' })
    return json(snapshot({ revision:2,activeRun:activeRun(['alpha','beta','gamma'],{ mode:'expedition',sect_id:'sect_1',guard:100,return_posts:{ alpha:'home' } }) }))
  })
  await session.store.startRun([...session.store.party],'expedition',{ sect_id:'sect_1' })
  assert.equal(session.count('POST','/saves/1/duty/unassign'),0)
  assert.equal(session.store.state.active_run.return_posts.alpha,'home')
})

test('batch crafting sends quantity and grade once and uses the server inventory', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST','/saves/1/craft',request => {
    assert.deepEqual(request.body,{ recipe_id:'ju_qi_dan',revision:1,quantity:4,grade:2 })
    return json(snapshot({ revision:2,inventory:{ 'ju_qi_dan:g2':4 } }))
  })
  await session.store.craft('ju_qi_dan',4,2)
  assert.equal(session.store.state.inventory['ju_qi_dan:g2'],4)
  assert.match(session.store.notice,/2品.*4 颗/)
})

test('a lost atomic healing response recovers state without separate crafting or pill use', async t => {
  const session = harness({ 1:snapshot({ disciples:[disciple('alpha',{ injury_stacks:2 })] }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST','/saves/1/items/heal-party',request => {
    assert.deepEqual(request.body,{ party:['alpha'],revision:1 })
    session.saved.set(1,snapshot({ revision:2,inventory:{ ling_cao:4 },disciples:[disciple('alpha')] }))
    throw new TypeError('Healing committed, response lost')
  })
  await session.store.healParty(['alpha'])
  assert.equal(session.count('POST','/saves/1/items/heal-party'),1)
  assert.equal(session.count('POST','/saves/1/craft'),0)
  assert.equal(session.count('POST','/saves/1/items/use'),0)
  assert.equal(session.store.disciples[0].injury_stacks,0)
  assert.equal(session.store.revision,2)
})

test('facility preview from an older revision is discarded after a resource mutation', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const pending = deferred()
  session.respond('GET','/saves/1/facilities',() => pending.promise)
  const preview = session.store.previewFacilities()
  session.respond('POST','/saves/1/craft',() => json(snapshot({ revision:2 })))
  await session.store.craft('ju_qi_dan')
  pending.resolve(json({ revision:1,facilities:[{ id:'hall',upgradeable:true }] }))
  assert.equal(await preview,null)
})

test('arena submits only three selected fighters and mirrors guard and casualties', async t => {
  const session = harness({ 1:snapshot({ activeRun:activeRun(['alpha','beta','gamma','delta'],{ sect_id:'sect_1',guard:100 }) }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST','/saves/1/run/arena',request => {
    assert.deepEqual(request.body,{ party:['delta','beta','gamma'],revision:1 })
    return json(snapshot({ revision:2,activeRun:activeRun(['alpha','beta','gamma','delta'],{ sect_id:'sect_1',guard:70,arena_round:1,member_hp:{ alpha:100,beta:50,gamma:0,delta:70 } }) }))
  })
  await session.store.fightArena(['delta','beta','gamma'])
  assert.equal(session.store.state.active_run.guard,70)
  assert.equal(session.store.state.active_run.member_hp.gamma,0)
  assert.equal(session.count('POST','/saves/1/run/choose'),0)
})

test('returning to the same save does not accept a preview started before the switch', async t => {
  const session = harness({ 1:snapshot(),2:snapshot() })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const pending = deferred()
  session.respond('GET','/saves/1/facilities',() => pending.promise)
  const preview = session.store.previewFacilities()
  await session.store.switchSave(2)
  await session.store.switchSave(1)
  pending.resolve(json({revision:1,facilities:[{id:'hall'}]}))
  assert.equal(await preview,null)
})

test('garrison assignment applies the returned production without a separate unassignment', async t => {
  const session = harness({ 1:snapshot({ duty:['alpha'] }) })
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.respond('POST','/saves/1/garrison/assign',request => {
    assert.deepEqual(request.body,{ sect_id:'sect_1',disciple_id:'alpha',revision:1 })
    const response = snapshot({ revision:2 })
    response.state.sects=[{ id:'sect_1',conquered:true,garrison:[{ disciple_id:'alpha' }] }]
    response.production.garrisons={ sect_1:{ ling_mu:.75 } }
    return json(response)
  })
  await session.store.assignGarrison('sect_1','alpha')
  assert.equal(session.store.production.garrisons.sect_1.ling_mu,.75)
  assert.equal(session.store.state.duty_slots.length,0)
  assert.equal(session.count('POST','/saves/1/duty/unassign'),0)
})

test('settlement explains a returned disciple whose former post is full', async t => {
  const initial=snapshot({ activeRun:activeRun(['alpha'],{return_posts:{alpha:'home'},end_reason:'defeated'}) })
  initial.status='defeated'
  const session=harness({1:initial})
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const returned=snapshot({revision:2})
  returned.state.sects=[]
  session.respond('POST','/saves/1/run/settle',() => json({...returned,cleared:1,victory:false,loot:{}}))
  await session.store.settleRun()
  assert.match(session.store.notice,/未自动回岗.*甲弟子/)
  assert.equal(session.count('POST','/saves/1/duty/assign'),0)
})

test('a special-material shortage opens an already conquered source instead of home duty', async t => {
  const initial=snapshot()
  initial.state.sects=[
    { id:'unbeaten',name:'赤霞剑宗',material_id:'han_tie',special_material_id:'gong_fa_qi_pei',conquered:false,garrison:[] },
    { id:'held',name:'云岚剑宗',material_id:'chi_tong',special_material_id:'gong_fa_qi_pei',conquered:true,garrison:[] },
  ]
  const session=harness({1:initial})
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.catalog.production={ materials:{ han_tie:.25,gong_fa_qi_pei:0 } }
  assert.equal(session.store.planProduction('gong_fa_qi_pei'),'expedition')
  assert.equal(session.store.targetSectId,'held')
  assert.match(session.store.notice,/云岚剑宗.*驻守/)
  assert.equal(session.store.planProduction('han_tie'),'duty')
  assert.equal(session.store.productionTarget,'han_tie')
  assert.equal(session.calls.filter(call=>call.method==='POST' && call.path.includes('/duty/')).length,0)
})

test('an unconquered or undiscovered special-material source explains the next action', async t => {
  const initial=snapshot()
  initial.state.sects=[{ id:'unbeaten',name:'听雨丹宗',material_id:'ling_cao',special_material_id:'po_jing_ling_cai',conquered:false,garrison:[] }]
  const session=harness({1:initial})
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  session.store.catalog.production={ materials:{ po_jing_ling_cai:0,hu_chi_qi_pei:0 } }
  assert.equal(session.store.planProduction('po_jing_ling_cai'),'expedition')
  assert.equal(session.store.targetSectId,'unbeaten')
  assert.match(session.store.notice,/先攻克听雨丹宗/)
  assert.equal(session.store.planProduction('hu_chi_qi_pei'),'expedition')
  assert.equal(session.store.targetSectId,'')
  assert.match(session.store.notice,/升级宗门主殿/)
})
