import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import * as THREE from 'three'

const modelSource = await readFile(new URL('../src/rendering/hd2d/cityModel.ts', import.meta.url), 'utf8')
const modelOutput = ts.transpileModule(modelSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const modelUrl = `data:text/javascript;base64,${Buffer.from(modelOutput).toString('base64')}`
const { CITY_BUILDINGS, CITY_PLAZA, projectCityActors } = await import(modelUrl)
const motionSource = await readFile(new URL('../src/rendering/hd2d/cityMotion.ts', import.meta.url), 'utf8')
const motionOutput = ts.transpileModule(motionSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { sampleCityMotion } = await import(`data:text/javascript;base64,${Buffer.from(motionOutput).toString('base64')}`)
const residents = projectCityActors({ disciples: Array.from({ length: 16 }, (_, index) => ({
  id: `resident${index}`, template_id: `r${index}`, busy: false, injury_stacks: 0,
})), duty_slots: [], sects: [], active_run: null }, id => ({ name: id, image: '/local.png' }))

test('residents walk and pause on continuous deterministic routes without mutating their snapshot', () => {
  const actor = residents[0]
  const before = structuredClone(actor)
  let previous = sampleCityMotion(actor, 0), walked = false, paused = false
  const locations = new Set(), headings = new Set()
  for (let tick = 1; tick <= 1200; tick++) {
    const pose = sampleCityMotion(actor, tick / 10)
    assert.deepEqual(pose, sampleCityMotion(structuredClone(actor), tick / 10))
    assert.ok(Math.hypot(pose.x - previous.x, pose.z - previous.z) <= .071001, 'the route never teleports at a turn or loop boundary')
    assert.ok(Number.isFinite(pose.heading))
    if (pose.moving) headings.add(pose.heading.toFixed(6))
    if (pose.moving && previous.moving) {
      const dx = pose.x - previous.x, dz = pose.z - previous.z
      const distance = Math.hypot(dx, dz)
      if (distance > 1e-8) assert.ok((Math.sin(pose.heading) * dx + Math.cos(pose.heading) * dz) / distance > .999999,
        'the model faces the direction of its current route segment')
    }
    walked ||= pose.moving
    paused ||= !pose.moving
    locations.add(`${pose.x.toFixed(2)},${pose.z.toFixed(2)}`)
    previous = pose
  }
  assert.ok(walked && paused && locations.size > 20)
  assert.equal(headings.size, 4, 'the model turns along all four sides of the existing route')
  assert.deepEqual(actor, before)
  const sameSpot = { ...actor, id: 'another-resident' }
  assert.notDeepEqual(sampleCityMotion(actor, 3), sampleCityMotion(sameSpot, 3), 'identities stagger their walking and pauses')
})

test('duty, injury and reduced motion keep a resident at the stable ground anchor', () => {
  const base = residents[0]
  for (const [actor, reduced] of [[{ ...base, duty: true }, false], [{ ...base, injured: true }, false], [base, true]]) {
    for (const seconds of [0, 5, 30, 300]) {
      assert.deepEqual(sampleCityMotion(actor, seconds, reduced), { x: base.x, z: base.z, heading: 0, moving: false })
    }
  }
})

test('the full walking routes stay inside the open plaza and contact the real terrain', async () => {
  const buildingSource = await readFile(new URL('../src/rendering/hd2d/cityBuildings.ts', import.meta.url), 'utf8')
  const buildingOutput = ts.transpileModule(buildingSource, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(specifier === './cityModel' ? modelUrl : import.meta.resolve(specifier))}`)
  const { buildCityEnvironment, CITY_WORLD_SCALE } = await import(`data:text/javascript;base64,${Buffer.from(buildingOutput).toString('base64')}`)
  const previousDocument = globalThis.document
  globalThis.document = { createElement: () => ({ width: 0, height: 0, getContext: () => ({ fillStyle: '', fillRect() {} }) }) }
  let environment
  try { environment = buildCityEnvironment() } finally { globalThis.document = previousDocument }
  environment.group.scale.setScalar(CITY_WORLD_SCALE)
  environment.group.updateMatrixWorld(true)
  const ray = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0))
  try {
    for (const actor of residents) for (let seconds = 0; seconds <= 70; seconds += .5) {
      const pose = sampleCityMotion(actor, seconds)
      assert.ok(Math.abs(pose.x - CITY_PLAZA.x) < CITY_PLAZA.width / 2 - 1)
      assert.ok(Math.abs(pose.z - CITY_PLAZA.z) < CITY_PLAZA.depth / 2 - 1)
      assert.ok(CITY_BUILDINGS.every(building => Math.abs(pose.x - building.x) > building.width / 2 + 1.4
        || Math.abs(pose.z - building.z) > building.depth / 2 + 1.4), 'walking must clear buildings and their steps')
      ray.ray.origin.set(pose.x * CITY_WORLD_SCALE, 20, pose.z * CITY_WORLD_SCALE)
      const hit = ray.intersectObject(environment.group, true)[0]
      assert.ok(hit && hit.point.y >= .1 * CITY_WORLD_SCALE && hit.point.y <= .2 * CITY_WORLD_SCALE,
        `${actor.id} must stay on the plaza clear of lamps and other obstacles at ${pose.x},${pose.z}`)
      const plazaHit = ray.intersectObjects(environment.plazaSurfaces)[0]
      assert.ok(plazaHit && Math.abs(plazaHit.point.y - hit.point.y) < 1e-8, 'the fast plaza query matches the full scene height')
    }
  } finally { environment.dispose() }
})
