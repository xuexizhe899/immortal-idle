import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import * as THREE from 'three'

const source = await readFile(new URL('../src/rendering/hd2d/cityModel.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { clampCityCamera, projectCityActors } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

const disciple = (id, extra = {}) => ({ id, template_id: `template_${id}`, busy: false, injury_stacks: 0, ...extra })
const describe = id => ({ name: `姓名:${id}`, image: `/assets/${id}.png` })
const stateWith = disciples => ({ disciples, duty_slots: [], sects: [], active_run: null })

test('all idle anchors remain on terrain clear of building and lamp geometry', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  try {
    environment.group.updateMatrixWorld(true)
    const actors = projectCityActors(stateWith(Array.from({ length: 16 }, (_, index) => disciple(`idle${index}`))), describe)
    const ray = new THREE.Raycaster()
    for (const actor of actors) for (const [dx, dz] of [[0, 0], [.35, 0], [-.35, 0], [0, .35], [0, -.35]]) {
      ray.set(new THREE.Vector3(actor.x + dx, 20, actor.z + dz), new THREE.Vector3(0, -1, 0))
      const hit = ray.intersectObject(environment.group, true)[0]
      const building = hit && [...environment.buildings].find(([, group]) => {
        let object = hit.object
        while (object && object !== group) object = object.parent
        return object === group
      })?.[0]
      assert.ok(hit && hit.point.y <= .2, `${actor.id} at ${actor.x},${actor.z} overlaps ${building ?? hit?.object.type} at height ${hit?.point.y}`)
    }
  } finally { environment.dispose() }
})

test('city shows only residents and excludes all departure and garrison references', () => {
  const state = stateWith([
    disciple('resident'), disciple('party'), disciple('snapshot'), disciple('busy', { busy: true }), disciple('garrison'),
  ])
  state.active_run = { party: ['party'], party_snapshot: { combatants: [{ id: 'snapshot' }] } }
  state.sects = [{ garrison: [{ disciple_id: 'garrison' }] }]
  const before = structuredClone(state)

  assert.deepEqual(projectCityActors(state, describe).map(actor => actor.id), ['resident'])
  assert.deepEqual(state, before)
})

test('duty and injury displays follow the current snapshot and use resolved identity assets', () => {
  const state = stateWith([disciple('idle'), disciple('duty', { injury_stacks: 2 })])
  state.duty_slots = [{ disciple_id: 'duty' }]
  const actors = projectCityActors(state, describe)

  assert.equal(actors[0].id, 'duty')
  assert.equal(actors[0].duty, true)
  assert.equal(actors[0].injured, true)
  assert.equal(actors[0].name, '姓名:template_duty')
  assert.equal(actors[0].image, '/assets/template_duty.png')
  assert.equal(actors[1].duty, false)
  assert.equal(actors[1].injured, false)
  assert.notDeepEqual([actors[0].x, actors[0].z], [actors[1].x, actors[1].z])
})

test('scene population stays bounded while retaining actual duty residents', () => {
  const state = stateWith(Array.from({ length: 24 }, (_, index) => disciple(`d${index}`)))
  state.duty_slots = [{ disciple_id: 'd23' }]
  const actors = projectCityActors(state, describe)

  assert.equal(actors.length, 16)
  assert.equal(actors[0].id, 'd23')
  assert.equal(new Set(actors.map(actor => `${actor.x},${actor.z}`)).size, 16)
  assert.ok(actors.every(actor => Number.isFinite(actor.x) && Number.isFinite(actor.z)))
})

test('changing or unloading saves does not preserve characters or statuses from the previous save', () => {
  const first = stateWith([disciple('first', { injury_stacks: 1 })])
  first.duty_slots = [{ disciple_id: 'first' }]
  const prior = projectCityActors(first, describe)
  const second = stateWith([disciple('second')])

  assert.deepEqual(projectCityActors(null, describe), [])
  assert.deepEqual(projectCityActors(undefined, describe), [])
  assert.deepEqual(projectCityActors(second, describe).map(actor => [actor.id, actor.duty, actor.injured]), [['second', false, false]])
  assert.deepEqual(projectCityActors(first, describe), prior)
})

test('camera bounds keep dragging and zooming within the town without mutating the input', () => {
  const high = { x: 90, z: 30, zoom: 9 }
  const low = { x: -90, z: -30, zoom: .01 }

  assert.deepEqual(clampCityCamera(high), { x: 16, z: 12, zoom: 2 })
  assert.deepEqual(clampCityCamera(low), { x: -16, z: -12, zoom: .75 })
  assert.deepEqual(clampCityCamera({ x: 3, z: -4, zoom: 1.2 }), { x: 3, z: -4, zoom: 1.2 })
  assert.deepEqual(high, { x: 90, z: 30, zoom: 9 })
  assert.deepEqual(low, { x: -90, z: -30, zoom: .01 })
})
