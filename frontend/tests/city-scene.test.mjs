import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import * as THREE from 'three'

const source = await readFile(new URL('../src/rendering/hd2d/cityModel.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { CITY_BUILDINGS, CITY_BUILDING_PATHS, CITY_PLAZA, clampCityCamera, projectCityActors } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

const disciple = (id, extra = {}) => ({ id, template_id: `template_${id}`, busy: false, injury_stacks: 0, ...extra })
const describe = id => ({ name: `姓名:${id}`, image: `/assets/${id}.png` })
const stateWith = disciples => ({ disciples, duty_slots: [], sects: [], active_run: null })

test('all idle and duty anchors remain on terrain clear of building and lamp geometry', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment, CITY_WORLD_SCALE } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  environment.group.scale.setScalar(CITY_WORLD_SCALE)
  try {
    environment.group.updateMatrixWorld(true)
    const idleState = stateWith(Array.from({ length: 16 }, (_, index) => disciple(`idle${index}`)))
    const dutyState = stateWith(Array.from({ length: 16 }, (_, index) => disciple(`duty${index}`)))
    dutyState.duty_slots = dutyState.disciples.map(disciple => ({ disciple_id: disciple.id }))
    const actors = [...projectCityActors(idleState, describe), ...projectCityActors(dutyState, describe)]
    const ray = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0), .001, 3 * CITY_WORLD_SCALE)
    for (const actor of actors) for (const [dx, dz] of [[0, 0], [.35, 0], [-.35, 0], [0, .35], [0, -.35]]) {
      ray.ray.origin.set((actor.x + dx) * CITY_WORLD_SCALE, 2 * CITY_WORLD_SCALE, (actor.z + dz) * CITY_WORLD_SCALE)
      const hit = ray.intersectObject(environment.group, true)[0]
      const building = hit && [...environment.buildings].find(([, group]) => {
        let object = hit.object
        while (object && object !== group) object = object.parent
        return object === group
      })?.[0]
      assert.ok(hit && hit.point.y <= .2 * CITY_WORLD_SCALE,
        `${actor.id} at ${actor.x},${actor.z} overlaps ${building ?? hit?.object.type} at height ${hit?.point.y}`)
    }
  } finally { environment.dispose() }
})

test('the whole central plaza stays paved and free from buildings and tall decorations', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  environment.group.updateMatrixWorld(true)
  try {
    const left = CITY_PLAZA.x - CITY_PLAZA.width / 2, right = CITY_PLAZA.x + CITY_PLAZA.width / 2
    const back = CITY_PLAZA.z - CITY_PLAZA.depth / 2, front = CITY_PLAZA.z + CITY_PLAZA.depth / 2
    assert.ok(CITY_PLAZA.width >= 26 && CITY_PLAZA.depth >= 22)
    for (const [id, group] of environment.buildings) {
      const box = new THREE.Box3().setFromObject(group)
      assert.ok(box.max.x < left || box.min.x > right || box.max.z < back || box.min.z > front,
        `${id} geometry leaves the whole plaza clear`)
    }
    const ray = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0))
    for (let x = left + .5; x < right; x++) for (let z = back + .5; z < front; z++) {
      ray.ray.origin.set(x, 20, z)
      const hit = ray.intersectObject(environment.group, true)[0]
      assert.ok(hit && hit.point.y >= .1 && hit.point.y <= .2, `clear paved plaza at ${x},${z}`)
    }
  } finally { environment.dispose() }
})

test('every building entrance has an unblocked paved route to the edge of the plaza', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  environment.group.updateMatrixWorld(true)
  try {
    const ray = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0))
    assert.deepEqual(CITY_BUILDING_PATHS.map(path => path.id), CITY_BUILDINGS.map(building => building.id))
    for (const route of CITY_BUILDING_PATHS) {
      const building = CITY_BUILDINGS.find(building => building.id === route.id)
      const [startX, startZ] = route.points[0], [endX, endZ] = route.points.at(-1)
      assert.equal(startX, building.x)
      assert.ok(Math.abs(startZ - (building.z + building.depth / 2 + 1.4)) < .001)
      assert.ok(Math.abs(endX - CITY_PLAZA.x) <= CITY_PLAZA.width / 2 && Math.abs(endZ - CITY_PLAZA.z) <= CITY_PLAZA.depth / 2 + .001)
      assert.ok(Math.abs(Math.abs(endX - CITY_PLAZA.x) - CITY_PLAZA.width / 2) < .001
        || Math.abs(Math.abs(endZ - CITY_PLAZA.z) - CITY_PLAZA.depth / 2) < .001)
      const points = [[startX, startZ - .25], ...route.points]
      for (let index = 1; index < points.length; index++) {
        const [x1, z1] = points[index - 1], [x2, z2] = points[index]
        const samples = Math.ceil(Math.hypot(x2 - x1, z2 - z1) * 5)
        for (let sample = 0; sample <= samples; sample++) {
          const t = sample / samples
          const x = x1 + (x2 - x1) * t, z = z1 + (z2 - z1) * t
          ray.ray.origin.set(x, 20, z)
          const hit = ray.intersectObject(environment.group, true)[0]
          assert.ok(hit && hit.point.y > .02 && hit.point.y <= .2,
            `${route.id} has an open paved path at ${x},${z}, height ${hit?.point.y}`)
        }
      }
    }
  } finally { environment.dispose() }
})

test('expanded flat ground covers viewport corners at zoom and pan limits', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment, CITY_WORLD_SCALE } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  environment.group.scale.setScalar(CITY_WORLD_SCALE)
  environment.group.updateMatrixWorld(true)
  try {
    const bounds = new THREE.Box3().setFromObject(environment.ground).getSize(new THREE.Vector3())
    assert.ok(bounds.x >= 350 && bounds.z >= 350, 'the land extends well beyond the traversable camera area')

    for (const aspect of [16 / 9, .62]) {
      const span = Math.max(35, 43 / aspect)
      const probe = new THREE.OrthographicCamera(-span * aspect / 2, span * aspect / 2, span / 2, -span / 2, .1, 150)
      probe.position.set(27, 32, 38); probe.lookAt(0, 0, 0)
      const upY = new THREE.Vector3(0, 1, 0).applyQuaternion(probe.quaternion).y
      const minimumZoom = Math.max(.75, span * upY / (2 * (32 + .08 * CITY_WORLD_SCALE)))
      for (const zoom of [minimumZoom, 1.15, 2]) {
        for (const [x, z] of [[-16, -12], [-16, 12], [16, -12], [16, 12]]) {
          const camera = new THREE.OrthographicCamera(-span * aspect / 2, span * aspect / 2, span / 2, -span / 2, .1, 150)
          const center = new THREE.Vector3(x, 0, z)
          camera.zoom = zoom
          camera.position.copy(center).add(new THREE.Vector3(27, 32, 38))
          camera.lookAt(center)
          camera.updateProjectionMatrix()
          camera.updateMatrixWorld(true)
          for (const [screenX, screenY] of [[-1, -1], [-1, 1], [1, -1], [1, 1]]) {
            const ray = new THREE.Raycaster()
            ray.setFromCamera(new THREE.Vector2(screenX, screenY), camera)
            const hit = ray.intersectObject(environment.ground)[0]
            assert.ok(hit, `ground visible at ${aspect} aspect, zoom ${zoom}, pan ${x},${z}`)
          }
        }
      }
    }
  } finally { environment.dispose() }
})

test('stone paths continue from town into the open plain in all four directions', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel'
      ? `data:text/javascript;base64,${Buffer.from(output).toString('base64')}` : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment, CITY_WORLD_SCALE } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  const environment = buildCityEnvironment()
  globalThis.document = previousDocument
  environment.group.scale.setScalar(CITY_WORLD_SCALE)
  environment.group.updateMatrixWorld(true)
  try {
    const samples = [
      ...[-16, -30, -52].map(z => [8.5, z]), ...[17, 30, 52].map(z => [0, z]),
      ...[17, 30, 52].map(x => [x, -1.5]), ...[-17, -30, -52].map(x => [x, -1.5]),
    ]
    for (const [x, z] of samples) {
      const ray = new THREE.Raycaster(new THREE.Vector3(x * CITY_WORLD_SCALE, 4, z * CITY_WORLD_SCALE), new THREE.Vector3(0, -1, 0))
      const hit = ray.intersectObject(environment.group, true)[0]
      assert.ok(hit && hit.point.y > .02 * CITY_WORLD_SCALE,
        `the route at ${x},${z} rises from the plain surface`)
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
  assert.equal(clampCityCamera({ x: 0, z: 0, zoom: .75 }, .92).zoom, .92)
  assert.deepEqual(high, { x: 90, z: 30, zoom: 9 })
  assert.deepEqual(low, { x: -90, z: -30, zoom: .01 })
})
