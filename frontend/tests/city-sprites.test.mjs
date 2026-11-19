import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as THREE from 'three'
import ts from 'typescript'

const compilerOptions = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
async function moduleUrl(path, imports = {}) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, { compilerOptions }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(imports[specifier] ?? import.meta.resolve(specifier))}`)
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}
const modelUrl = await moduleUrl('../src/rendering/characters/cultivatorModel.ts')
const { createCityActors } = await import(await moduleUrl('../src/rendering/hd2d/pixelSprites.ts', {
  '../characters/cultivatorModel': modelUrl,
}))
const { sampleCityMotion } = await import(await moduleUrl('../src/rendering/hd2d/cityMotion.ts'))
const actor = (id, extra = {}) => ({
  id, templateId: 'guanyu', image: '', name: id, x: 0, z: 0, injured: false, duty: false, ...extra,
})
function fixture(t) {
  const models = createCityActors()
  t.after(() => models.dispose())
  return models
}
function resources(root) {
  const result = new Set()
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    result.add(object.geometry)
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) result.add(material)
  })
  return [...result]
}
function disposalCounts(root) {
  return resources(root).map(resource => {
    let count = 0
    resource.addEventListener('dispose', () => count++)
    return () => count
  })
}
function jointPose(root) {
  return ['leftUpperArm', 'rightUpperArm', 'leftThigh', 'rightThigh', 'leftLowerLeg', 'rightLowerLeg'].map(name => {
    const joint = root.getObjectByName(name)
    assert.ok(joint?.isGroup, `the character has the articulated ${name} joint`)
    return joint.rotation.toArray().slice(0, 3)
  })
}
function owner(object) {
  while (object && !object.userData.kind) object = object.parent
  return object?.userData
}

test('city residents are volumetric articulated models without loading portrait textures', t => {
  t.mock.method(THREE.TextureLoader.prototype, 'load', () => { throw new Error('city models must not request portrait textures') })
  const models = fixture(t)
  models.sync([actor('resident'), actor('without-image', { templateId: 'zhugeliang', x: 4 })], () => .17)
  assert.equal(models.actors.size, 2)
  const root = models.actors.get('resident')
  assert.ok(root.isGroup)
  assert.deepEqual(root.position.toArray(), [0, .17, 0])
  assert.equal(root.userData.id, 'resident')
  jointPose(root)
  root.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(root)
  const size = box.getSize(new THREE.Vector3())
  assert.ok(size.y > 2.4 && size.y < 3.1)
  assert.ok(size.z > .35, 'the body has physical depth rather than a portrait plane')
  assert.ok(Math.abs(box.min.y - .17) < .02, 'the model feet start at the sampled ground')
  const torso = root.getObjectByName('torso')
  assert.ok(new THREE.Box3().setFromObject(torso).getSize(new THREE.Vector3()).z > .2)
  let meshes = 0
  root.traverse(object => { if (object.isMesh) meshes++ })
  assert.ok(meshes >= 12, 'body, clothing and equipment are actual separate geometry')
})

test('movement keeps the model and geometry, turns toward travel, animates joints and keeps its shadow grounded', t => {
  const models = fixture(t)
  models.group.scale.setScalar(1.1)
  models.sync([actor('moving'), actor('stationary', { x: -4, z: 2 })], () => .17)
  const root = models.actors.get('moving'), stationary = models.actors.get('stationary')
  const shadow = models.group.children.find(object => object.userData.groundShadow)
  const originalResources = resources(root), disposals = disposalCounts(root)
  const stationaryPosition = stationary.position.clone()
  const position = { x: 3.5, z: -1.5, heading: Math.PI / 2, moving: true }
  models.move('moving', position, .23, .13)
  const firstPose = jointPose(root)
  models.move('moving', position, .23, .46)
  assert.notDeepEqual(jointPose(root), firstPose, 'walking bends joints instead of sliding a flat image')
  assert.strictEqual(models.actors.get('moving'), root)
  assert.deepEqual(root.position.toArray(), [3.5, .23, -1.5])
  assert.equal(root.rotation.y, Math.PI / 2)
  const forward = new THREE.Vector3(0, 0, 1).applyQuaternion(root.quaternion)
  assert.ok(forward.distanceTo(new THREE.Vector3(1, 0, 0)) < 1e-10)
  assert.equal(root.userData.groundY, .23)
  assert.deepEqual(shadow.position.toArray(), [3.5, .23 + .012, -1.5])
  assert.deepEqual(stationary.position.toArray(), stationaryPosition.toArray())
  assert.deepEqual(resources(root), originalResources)
  assert.ok(disposals.every(count => count() === 0))
})

test('duty, injury, reduced motion and route pauses keep internal joints still as time advances', t => {
  const models = fixture(t)
  const resident = actor('resident')
  models.sync([resident])
  const root = models.actors.get('resident')
  for (const [current, reduced] of [[{ ...resident, duty: true }, false], [{ ...resident, injured: true }, false], [resident, true]]) {
    models.move(resident.id, sampleCityMotion(current, 1, reduced), .17, 1)
    const still = jointPose(root)
    models.move(resident.id, sampleCityMotion(current, 20, reduced), .17, 20)
    assert.deepEqual(jointPose(root), still)
    assert.deepEqual(root.position.toArray(), [resident.x, .17, resident.z])
  }
  const paused = { x: 2, z: 3, heading: Math.PI, moving: false }
  models.move(resident.id, paused, .17, 1)
  const still = jointPose(root)
  models.move(resident.id, paused, .17, 20)
  assert.deepEqual(jointPose(root), still)
  assert.equal(root.rotation.y, Math.PI)
})

test('real Three rays select body geometry in depth order and miss empty silhouette space', t => {
  const models = fixture(t)
  models.sync([actor('resident')], () => .17)
  models.group.updateMatrixWorld(true)
  const root = models.actors.get('resident')
  const ray = new THREE.Raycaster(new THREE.Vector3(0, 1.6, 8), new THREE.Vector3(0, 0, -1))
  const bodyHit = ray.intersectObject(models.group, true)[0]
  assert.ok(bodyHit?.object.isMesh)
  assert.equal(owner(bodyHit.object).id, 'resident')
  assert.ok(Math.abs(bodyHit.point.distanceTo(ray.ray.origin) - bodyHit.distance) < 1e-8)
  const sideRay = new THREE.Raycaster(new THREE.Vector3(8, 1.6, 0), new THREE.Vector3(-1, 0, 0))
  assert.ok(sideRay.intersectObject(root, true).length, 'a model also has a real side surface')

  const occluder = new THREE.Mesh(new THREE.BoxGeometry(1, 1, .3), new THREE.MeshBasicMaterial())
  t.after(() => { occluder.geometry.dispose(); occluder.material.dispose() })
  occluder.position.set(0, 1.6, 3)
  occluder.updateMatrixWorld(true)
  assert.strictEqual(ray.intersectObjects([root, occluder], true)[0].object, occluder)
  occluder.position.z = -3
  occluder.updateMatrixWorld(true)
  assert.equal(owner(ray.intersectObjects([root, occluder], true)[0].object).id, 'resident')

  const box = new THREE.Box3().setFromObject(root)
  let hits = 0, empty = 0
  for (let x = 1; x < 10; x++) for (let y = 1; y < 10; y++) {
    ray.ray.origin.set(THREE.MathUtils.lerp(box.min.x, box.max.x, x / 10), THREE.MathUtils.lerp(box.min.y, box.max.y, y / 10), 8)
    if (ray.intersectObject(root, true).length) hits++
    else empty++
  }
  assert.ok(hits > 0 && empty > 0, 'gaps around body parts remain clickable space rather than a full sprite rectangle')
  for (const shadow of models.group.children.filter(object => object.userData.groundShadow)) {
    const down = new THREE.Raycaster(shadow.position.clone().add(new THREE.Vector3(0, 3, 0)), new THREE.Vector3(0, -1, 0))
    assert.deepEqual(down.intersectObject(shadow), [], 'contact shadows do not intercept selection')
  }
})

test('sync reuses unchanged identities, removes absent or changed templates and disposes each owned resource once', t => {
  const models = fixture(t)
  models.sync([actor('first'), actor('second', { x: 3 })])
  const first = models.actors.get('first'), second = models.actors.get('second')
  const firstDisposals = disposalCounts(first), secondDisposals = disposalCounts(second)
  const shadow = models.group.children.find(object => object.userData.groundShadow)
  const shadowDisposals = disposalCounts(shadow)
  models.sync([actor('first', { injured: true }), actor('third')])
  assert.strictEqual(models.actors.get('first'), first)
  assert.equal(second.parent, null)
  assert.ok(secondDisposals.every(count => count() === 1))
  assert.ok(firstDisposals.every(count => count() === 0))
  assert.deepEqual([...models.actors.keys()], ['first', 'third'])
  models.sync([actor('first', { templateId: 'zhugeliang' })])
  assert.notStrictEqual(models.actors.get('first'), first)
  assert.ok(firstDisposals.every(count => count() === 1))
  const finalDisposals = disposalCounts(models.actors.get('first'))
  models.dispose()
  models.dispose()
  assert.equal(models.actors.size, 0)
  assert.equal(models.group.children.length, 0)
  assert.ok(finalDisposals.every(count => count() === 1))
  assert.ok(shadowDisposals.every(count => count() === 1))
})
