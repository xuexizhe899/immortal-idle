import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as THREE from 'three'
import ts from 'typescript'

const source = await readFile(new URL('../src/rendering/hd2d/pixelSprites.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
  .replace("from 'three'", `from ${JSON.stringify(import.meta.resolve('three'))}`)
const { createCityActors } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

const actor = (id, image = '/shared.png') => ({ id, image, name: id, x: 0, z: 0, injured: false, duty: false })
const disposeCount = resource => {
  let count = 0
  resource.addEventListener('dispose', () => count++)
  return () => count
}

function fixture(t) {
  const pending = []
  const textureDisposals = new Map()
  let loaded = 0, failed = 0, closed = false
  t.mock.method(THREE.TextureLoader.prototype, 'load', (url, onLoad, _onProgress, onError) => {
    const texture = new THREE.Texture()
    textureDisposals.set(texture, disposeCount(texture))
    pending.push({ url, texture, onLoad, onError })
    return texture
  })
  const priorDocument = Object.getOwnPropertyDescriptor(globalThis, 'document')
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    createElement(tag) {
      assert.equal(tag, 'canvas')
      let drawn
      return { width: 0, height: 0, getContext(kind) {
        assert.equal(kind, '2d')
        return {
          drawImage(image) { drawn = image },
          getImageData() {
            const data = new Uint8ClampedArray(drawn.width * drawn.height * 4)
            for (let index = 0; index < drawn.alpha.length; index++) data[index * 4 + 3] = drawn.alpha[index]
            return { data }
          },
        }
      } }
    },
  } })
  const sprites = createCityActors(() => failed++, () => loaded++)
  const close = () => { if (!closed) { sprites.dispose(); closed = true } }
  t.after(() => {
    close()
    if (priorDocument) Object.defineProperty(globalThis, 'document', priorDocument)
    else delete globalThis.document
  })
  return {
    sprites, pending, textureDisposals, close,
    get loaded() { return loaded },
    get failed() { return failed },
    load(url, width = 4, height = 4, alpha = Array(width * height).fill(255)) {
      const request = pending.find(item => item.url === url)
      assert.ok(request, `expected a pending image load for ${url}`)
      request.texture.image = { width, height, alpha }
      request.onLoad(request.texture)
      return request.texture
    },
  }
}

function cameraAt(x = 12, y = 15, z = 20) {
  const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, .1, 100)
  camera.position.set(x, y, z)
  camera.lookAt(0, 0, 0)
  camera.updateProjectionMatrix()
  camera.updateMatrixWorld(true)
  return camera
}

function rayHit(sprites, camera, id, u, v) {
  sprites.group.updateMatrixWorld(true)
  const mesh = sprites.actors.get(id)
  const point = mesh.localToWorld(new THREE.Vector3(u - .5, v * 2.7, 0))
  const forward = camera.getWorldDirection(new THREE.Vector3())
  const ray = new THREE.Raycaster(point.clone().addScaledVector(forward, -50), forward)
  const hit = ray.intersectObject(mesh)[0]
  assert.ok(hit, 'the real Three.js ray must intersect the sprite rectangle')
  return hit
}

test('a ray through transparent art continues behind the sprite while an opaque pixel can be selected', t => {
  const f = fixture(t)
  const camera = cameraAt()
  f.sprites.sync([actor('disciple')], camera)
  f.load('/shared.png', 4, 4, [0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 255])

  assert.equal(f.sprites.hitDepth(rayHit(f.sprites, camera, 'disciple', .25, .6), camera), null)
  assert.ok(Number.isFinite(f.sprites.hitDepth(rayHit(f.sprites, camera, 'disciple', .75, .6), camera)))
})

test('opaque sprite picking follows the scaled foot depth and remains finite at a steep camera angle', t => {
  const f = fixture(t)
  for (const scale of [1, 1.1]) for (const camera of [cameraAt(), cameraAt(0, 20, 0)]) {
    f.sprites.group.scale.setScalar(scale)
    f.sprites.sync([actor('disciple')], camera)
    if (!f.loaded) f.load('/shared.png')
    f.sprites.move('disciple', { x: 2, z: -3, bob: .02 }, .17)
    const mesh = f.sprites.actors.get('disciple')
    const hit = rayHit(f.sprites, camera, 'disciple', .75, .8)
    const local = mesh.worldToLocal(hit.point.clone())
    const foot = mesh.localToWorld(new THREE.Vector3(local.x, 0, 0))
    const forward = camera.getWorldDirection(new THREE.Vector3())
    const cameraUp = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1)
    const baseDepth = foot.sub(camera.position).dot(forward)
    const expected = baseDepth + local.y * mesh.scale.y * scale * forward.y / Math.max(Math.abs(cameraUp.y), .2)
    const depth = f.sprites.hitDepth(hit, camera)

    assert.ok(Number.isFinite(depth))
    assert.ok(Math.abs(depth - expected) < 1e-8)
    assert.ok(Math.abs(depth - baseDepth) > .1, 'selection must account for the height above the foot')
    const shader = { vertexShader: '#include <project_vertex>' }
    mesh.material.onBeforeCompile(shader)
    assert.match(shader.vertexShader, /foot\.z\s*\+=\s*rise\s*\*\s*up\.z\s*\/\s*max\(abs\(up\.y\),\s*0\.2\)/)
  }
})

test('moving a resident keeps its identity and resources while its contact shadow follows the new ground', t => {
  const f = fixture(t)
  const camera = cameraAt()
  f.sprites.group.scale.setScalar(1.1)
  f.sprites.sync([actor('moving'), { ...actor('stationary'), x: -4, z: 2 }], camera)
  const texture = f.load('/shared.png', 4, 4, [0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 255])
  const mesh = f.sprites.actors.get('moving')
  const stationary = f.sprites.actors.get('stationary')
  const shadow = f.sprites.group.children.find(child => !child.userData.kind)
  const geometry = mesh.geometry, material = mesh.material
  const geometryDisposals = disposeCount(geometry), materialDisposals = disposeCount(material)
  const stationaryPosition = stationary.position.clone()

  f.sprites.move('moving', { x: 3.5, z: -1.5, bob: .04 }, .17)

  assert.strictEqual(f.sprites.actors.get('moving'), mesh)
  assert.equal(mesh.userData.id, 'moving')
  assert.deepEqual(mesh.position.toArray(), [3.5, .17 + .025 + .04, -1.5])
  assert.equal(mesh.userData.groundY, .17 + .025)
  assert.deepEqual(shadow.position.toArray(), [3.5, .17 + .012, -1.5])
  assert.deepEqual(stationary.position.toArray(), stationaryPosition.toArray())
  assert.strictEqual(mesh.geometry, geometry)
  assert.strictEqual(mesh.material, material)
  assert.strictEqual(mesh.material.map, texture)
  assert.equal(f.pending.length, 1, 'movement does not issue a new image request')
  assert.deepEqual([geometryDisposals(), materialDisposals(), f.textureDisposals.get(texture)()], [0, 0, 0])
  assert.equal(f.sprites.hitDepth(rayHit(f.sprites, camera, 'moving', .25, .6), camera), null)
  const opaqueHit = rayHit(f.sprites, camera, 'moving', .75, .6)
  assert.equal(opaqueHit.object.userData.id, 'moving')
  assert.ok(Number.isFinite(f.sprites.hitDepth(opaqueHit, camera)))
})

test('asynchronous image completion requests a new draw and updates all cached sprite proportions', t => {
  const f = fixture(t)
  f.sprites.sync([actor('first'), actor('second')], cameraAt())
  assert.equal(f.loaded, 0)
  assert.equal(f.pending.length, 1)
  const texture = f.load('/shared.png', 8, 4)

  assert.equal(f.loaded, 1, 'the host can redraw even when reduced motion has stopped its animation loop')
  assert.equal(f.failed, 0)
  for (const mesh of f.sprites.actors.values()) {
    assert.strictEqual(mesh.material.map, texture)
    assert.equal(mesh.scale.x, 5.4)
  }
})

test('sprites and contact shadows follow the ground height at each resident position', t => {
  const f = fixture(t)
  const residents = [{ ...actor('grass'), x: 2 }, { ...actor('plaza'), x: 4 }]
  f.sprites.sync(residents, cameraAt(), x => x === 2 ? .04 : .17)
  assert.equal(f.sprites.actors.get('grass').position.y, .04 + .025)
  assert.equal(f.sprites.actors.get('plaza').position.y, .17 + .025)
  const shadows = f.sprites.group.children.filter(child => !child.userData.kind)
  assert.deepEqual(shadows.map(shadow => shadow.position.y), [.04 + .012, .17 + .012])
})

test('sync replaces actor meshes and final disposal releases shared textures and shadows once', t => {
  const f = fixture(t)
  const camera = cameraAt()
  f.sprites.sync([actor('first'), actor('second')], camera)
  const firstTexture = f.load('/shared.png')
  const oldMeshes = [...f.sprites.actors.values()]
  const oldDisposals = oldMeshes.map(mesh => [disposeCount(mesh.geometry), disposeCount(mesh.material)])
  const shadow = f.sprites.group.children.find(child => !child.userData.kind)
  const shadowGeometryDisposals = disposeCount(shadow.geometry)
  const shadowMaterialDisposals = disposeCount(shadow.material)
  const staleHit = rayHit(f.sprites, camera, 'first', .75, .6)

  f.sprites.sync([actor('replacement', '/replacement.png')], camera)
  const replacementTexture = f.load('/replacement.png')
  const mesh = f.sprites.actors.get('replacement')
  const geometryDisposals = disposeCount(mesh.geometry)
  const materialDisposals = disposeCount(mesh.material)
  assert.deepEqual([...f.sprites.actors.keys()], ['replacement'])
  assert.equal(f.sprites.group.children.length, 2)
  assert.equal(f.sprites.hitDepth(staleHit, camera), null)
  for (const [geometry, material] of oldDisposals) assert.deepEqual([geometry(), material()], [1, 1])
  assert.equal(f.textureDisposals.get(firstTexture)(), 0)

  f.close()
  assert.equal(f.sprites.actors.size, 0)
  assert.equal(f.sprites.group.children.length, 0)
  assert.equal(f.textureDisposals.get(firstTexture)(), 1)
  assert.equal(f.textureDisposals.get(replacementTexture)(), 1)
  assert.deepEqual([geometryDisposals(), materialDisposals(), shadowGeometryDisposals(), shadowMaterialDisposals()], [1, 1, 1, 1])
})

test('an image completing after disposal neither redraws nor releases its cached texture twice', t => {
  const f = fixture(t)
  f.sprites.sync([actor('pending')], cameraAt())
  const texture = f.pending[0].texture
  f.close()
  assert.equal(f.textureDisposals.get(texture)(), 1)

  f.load('/shared.png')
  assert.equal(f.loaded, 0)
  assert.equal(f.failed, 0)
  assert.equal(f.sprites.actors.size, 0)
  assert.equal(f.sprites.group.children.length, 0)
  assert.equal(f.textureDisposals.get(texture)(), 1)
})
