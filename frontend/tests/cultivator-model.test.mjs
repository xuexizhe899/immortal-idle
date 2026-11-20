import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as THREE from 'three'
import ts from 'typescript'

const source = await readFile(new URL('../src/rendering/characters/cultivatorModel.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
  .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(import.meta.resolve(specifier))}`)
const { createCultivatorModel } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
const identities = ['zhugeliang', 'guanyu', 'change', 'baisuzhen', 'dufu', 'houyi', 'huatuo', 'jingwei', 'libai', 'nezha', 'yangjian', 'yuefei', 'zhangfei', 'zhangheng', 'zhaoyun', 'zhouyu']
const joints = ['head', 'torso', 'leftUpperArm', 'rightUpperArm', 'leftForearm', 'rightForearm', 'leftThigh', 'rightThigh', 'leftLowerLeg', 'rightLowerLeg', 'leftFoot', 'rightFoot', 'weapon']

function fixture(t, templateId = 'guanyu', extra = {}) {
  const actor = createCultivatorModel({ templateId, ...extra })
  t.after(() => actor.dispose())
  return actor
}
function meshes(root) {
  const result = []
  root.traverse(part => { if (part.isMesh) result.push(part) })
  return result
}
function resources(root) {
  const result = new Set()
  for (const part of meshes(root)) { result.add(part.geometry); result.add(part.material) }
  return [...result]
}
function bounds(root) { root.updateWorldMatrix(true, true); return new THREE.Box3().setFromObject(root) }
function faceWidth(head) {
  const face = new THREE.Box3(); const point = new THREE.Vector3()
  // 只量下颌至额头的前部截面，双髻、高冠和长须属于身份轮廓，不是头骨尺寸。
  for (const part of meshes(head)) {
    const positions = part.geometry.getAttribute('position')
    for (let index = 0; index < positions.count; index++) {
      point.fromBufferAttribute(positions, index).applyMatrix4(part.matrixWorld); head.worldToLocal(point)
      if (point.y > .09 && point.y < .30 && point.z > .07) face.expandByPoint(point)
    }
  }
  assert.ok(!face.isEmpty(), 'the model has a measurable solid face')
  return face.getSize(new THREE.Vector3()).x
}
function geometryIdentity(root) {
  root.updateWorldMatrix(true, true)
  const vertices = []; const point = new THREE.Vector3()
  for (const mesh of meshes(root)) {
    const positions = mesh.geometry.getAttribute('position')
    for (let index = 0; index < positions.count; index++) {
      point.fromBufferAttribute(positions, index).applyMatrix4(mesh.matrixWorld)
      vertices.push(point.toArray().map(value => value.toFixed(4)).join(','))
    }
  }
  return createHash('sha256').update(vertices.sort().join(';')).digest('hex')
}
function jointState(root) { return joints.map(name => root.getObjectByName(name).rotation.toArray().slice(0, 3)) }

test('all sixteen identities have adult proportions, solid shaded bodies and the same ground origin', t => {
  t.mock.method(THREE.TextureLoader.prototype, 'load', () => { throw new Error('the model must not load portrait planes') })
  for (const templateId of identities) {
    const actor = fixture(t, templateId); const box = bounds(actor.group); const size = box.getSize(new THREE.Vector3())
    assert.ok(Math.abs(box.min.y) < 1e-5, `${templateId}: the shoes start at y=0`)
    assert.ok(size.y > 2.5 && size.y < 2.85, `${templateId}: adult body height stays near 2.7`)
    assert.ok(size.z > .4, `${templateId}: the body has real front-to-back volume`)
    for (const name of joints) assert.ok(actor.group.getObjectByName(name)?.isGroup, `${templateId}: articulated ${name}`)
    const head = actor.group.getObjectByName('head')
    assert.ok(faceWidth(head) / size.y < .19, `${templateId}: the head is not a chibi-sized silhouette`)
    assert.ok(head.getWorldPosition(new THREE.Vector3()).y / size.y > .74, `${templateId}: the neck sits above an adult-length trunk and legs`)
    for (const side of ['left', 'right']) {
      const hip = actor.group.getObjectByName(`${side}Thigh`).getWorldPosition(new THREE.Vector3())
      const foot = actor.group.getObjectByName(`${side}Foot`).getWorldPosition(new THREE.Vector3())
      assert.ok((hip.y - foot.y) / size.y > .33, `${templateId}: the legs retain adult proportions`)
    }
    for (const part of meshes(actor.group)) {
      assert.ok(part.material.isMeshStandardMaterial && !part.material.map)
      assert.ok(part.castShadow && part.receiveShadow)
      part.geometry.computeBoundingBox()
      const volume = part.geometry.boundingBox.getSize(new THREE.Vector3())
      assert.ok(volume.x > .001 && volume.y > .001 && volume.z > .001, `${templateId}: every mesh has thickness`)
      const positions = part.geometry.getAttribute('position'); const normals = part.geometry.getAttribute('normal')
      assert.equal(normals.count, positions.count)
      assert.ok([...positions.array, ...normals.array].every(Number.isFinite), `${templateId}: merged vertex data stays finite`)
    }
  }
})

test('identity differences remain geometric even when all material colors are ignored', t => {
  const shapes = new Set()
  for (const templateId of identities) shapes.add(geometryIdentity(fixture(t, templateId).group))
  assert.equal(shapes.size, identities.length, 'the sixteen characters cannot be palette swaps of one body')
  const scholar = fixture(t, 'zhugeliang').group; const warrior = fixture(t, 'guanyu').group; const goddess = fixture(t, 'change').group
  const shoulderSpan = root => root.getObjectByName('rightUpperArm').position.x - root.getObjectByName('leftUpperArm').position.x
  assert.ok(shoulderSpan(warrior) > shoulderSpan(scholar) && shoulderSpan(scholar) > shoulderSpan(goddess))
  assert.ok(bounds(warrior.getObjectByName('weapon')).getSize(new THREE.Vector3()).y > 1.8, 'the warrior keeps a full-length polearm')
  assert.ok(bounds(scholar.getObjectByName('weapon')).getSize(new THREE.Vector3()).x > .2, 'the scholar keeps the feather fan silhouette')
})

test('static meshes share one draw per material and direct joint while the articulated draw budget stays bounded', t => {
  let total = 0
  for (const templateId of identities) {
    const root = fixture(t, templateId).group; const count = meshes(root).length
    assert.ok(count <= 52, `${templateId}: ${count} meshes exceeds the articulated model budget`)
    total += count
    root.traverse(parent => {
      const materials = parent.children.filter(part => part.isMesh).map(part => part.material)
      assert.equal(new Set(materials).size, materials.length, `${templateId}: fixed sibling meshes of one material should be merged`)
    })
  }
  assert.ok(total <= 750, `the sixteen models use ${total} meshes before shadow passes`)
})

test('walking bends hips and knees, keeps a support foot grounded and reuses every GPU resource', t => {
  const actor = fixture(t); const before = resources(actor.group)
  actor.pose({ time: .21, walking: true }); const first = jointState(actor.group)
  const feet = ['leftFoot', 'rightFoot'].map(name => bounds(actor.group.getObjectByName(name)).min.y)
  assert.ok(feet.every(y => y > -1e-5) && feet.some(y => Math.abs(y) < 1e-5), 'the support sole stays on the floor during a step')
  actor.pose({ time: .63, walking: true })
  assert.notDeepEqual(jointState(actor.group), first)
  assert.notEqual(actor.group.getObjectByName('leftThigh').rotation.x, actor.group.getObjectByName('rightThigh').rotation.x)
  assert.deepEqual(resources(actor.group), before)
  actor.pose({ time: 0, walking: false }); const resting = jointState(actor.group)
  actor.pose({ time: 0, walking: false }); assert.deepEqual(jointState(actor.group), resting)
})

test('windup, contact and recovery articulate the weapon while ranged contact raises a casting hand', t => {
  const actor = fixture(t); const initial = resources(actor.group); const poses = []
  actor.pose({ time: 0 }); const idleWeaponReach = bounds(actor.group.getObjectByName('weapon')).max.z
  for (const phase of ['windup', 'contact', 'recover']) { actor.pose({ time: 0, phase, melee: true }); poses.push(jointState(actor.group)) }
  assert.notDeepEqual(poses[0], poses[1]); assert.notDeepEqual(poses[1], poses[2])
  actor.pose({ time: 0, phase: 'contact', melee: true })
  assert.ok(bounds(actor.group.getObjectByName('weapon')).max.z > idleWeaponReach + .3, 'melee contact visibly extends the polearm toward +z')
  const melee = jointState(actor.group)
  actor.pose({ time: 0, phase: 'contact', melee: false })
  assert.notDeepEqual(jointState(actor.group), melee)
  const hand = actor.group.getObjectByName('leftHand').getWorldPosition(new THREE.Vector3())
  assert.ok(hand.z > .5 && hand.y > 1.5, 'ranged contact presents the raised casting hand rather than another weapon slash')
  assert.deepEqual(resources(actor.group), initial)
})

test('all pose modes preserve scene-owned root position, orientation and scale', t => {
  const actor = fixture(t, 'zhaoyun')
  actor.group.position.set(7, 2, -3); actor.group.rotation.set(.1, 1.2, -.05); actor.group.scale.setScalar(1.3)
  const external = { position: actor.group.position.toArray(), quaternion: actor.group.quaternion.toArray(), scale: actor.group.scale.toArray() }
  for (const pose of [{ walking: true }, { phase: 'windup' }, { phase: 'contact' }, { phase: 'contact', melee: false }, { phase: 'recover' }, { hit: true }, { fallen: true }, {}]) {
    actor.pose({ time: .21, ...pose })
    assert.deepEqual({ position: actor.group.position.toArray(), quaternion: actor.group.quaternion.toArray(), scale: actor.group.scale.toArray() }, external)
  }
})

test('hit and fallen poses return cleanly to rest without retaining damage tint or collapsed joints', t => {
  const actor = fixture(t, 'zhugeliang'); const rest = jointState(actor.group)
  actor.pose({ time: 0, hit: true })
  assert.ok(meshes(actor.group).every(part => part.material.emissiveIntensity > 0))
  actor.pose({ time: 0, fallen: true })
  assert.ok(Math.abs(actor.group.getObjectByName('pelvis').rotation.z) > 1)
  actor.pose({ time: 0 })
  assert.deepEqual(jointState(actor.group), rest)
  assert.ok(meshes(actor.group).every(part => part.material.emissiveIntensity === 0))
  assert.ok(Math.abs(bounds(actor.group).min.y) < 1e-5)
})

test('each live geometry and material is disposed once even when shared or released repeatedly', () => {
  for (const templateId of identities) {
    const actor = createCultivatorModel({ templateId }); const counts = resources(actor.group).map(resource => {
      let count = 0; resource.addEventListener('dispose', () => count++); return () => count
    })
    actor.dispose(); actor.dispose(); actor.pose({ time: 1, walking: true })
    assert.ok(counts.every(count => count() === 1), `${templateId}: GPU ownership remains unique after merging`)
    assert.equal(actor.group.children.length, 0)
  }
})

test('unknown allied, enemy guard and sect master identities retain different solid silhouettes', t => {
  const shapes = [{}, { enemy: true }, { enemy: true, boss: true }].map(extra => {
    const actor = fixture(t, 'unknown-cultivator', extra)
    assert.ok(bounds(actor.group).getSize(new THREE.Vector3()).z > .4)
    return geometryIdentity(actor.group)
  })
  assert.equal(new Set(shapes).size, 3)
})
