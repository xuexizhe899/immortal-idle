import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as THREE from 'three'
import ts from 'typescript'

const compilerOptions = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
async function moduleUrl(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, { compilerOptions }).outputText
    .replace(/from '([^']+)'/g, (_match, specifier) => `from ${JSON.stringify(import.meta.resolve(specifier))}`)
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}
const { createCultivatorModel } = await import(await moduleUrl('../src/rendering/characters/cultivatorModel.ts'))
const { battleImpact } = await import(await moduleUrl('../src/rendering/battlePlayback.ts'))
const source = await readFile(new URL('../src/rendering/battleScene.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions }).outputText
  .replace(/^import .*\r?\n/gm, '').replace(/^export /gm, '')
const makeModule = new Function('THREE', 'createCultivatorModel', 'battleImpact', `${output}\nreturn { createBattleScene, battlePosition }`)

function fixture(t, { width = 390, height = 290, renderError = false } = {}) {
  let now = 0, sequence = 0, renderer, disconnected = 0, failures = 0, api
  const frames = new Map(), labels = []
  const document = new EventTarget(); document.hidden = false
  const canvas = new EventTarget()
  canvas.setAttribute = () => {}
  canvas.remove = () => { canvas.removed = true }
  class Renderer {
    constructor() { renderer = this; this.domElement = canvas; this.shadowMap = {}; this.disposals = 0; this.contextLosses = 0 }
    setPixelRatio() {}
    setSize() {}
    render(scene, camera) {
      this.scene = scene; this.camera = camera
      scene.updateMatrixWorld(true); camera.updateMatrixWorld(true)
      if (renderError) throw new Error('injected renderer failure')
    }
    dispose() { this.disposals++ }
    forceContextLoss() { this.contextLosses++ }
  }
  const replacements = {
    window: { devicePixelRatio: 1 }, document, performance: { now: () => now },
    requestAnimationFrame: callback => { const id = ++sequence; frames.set(id, callback); return id },
    cancelAnimationFrame: id => frames.delete(id),
    ResizeObserver: class {
      constructor(callback) { this.callback = callback }
      observe() { this.callback() }
      disconnect() { disconnected++ }
    },
  }
  const original = Object.fromEntries(Object.keys(replacements).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  for (const [key, value] of Object.entries(replacements)) Object.defineProperty(globalThis, key, { configurable: true, writable: true, value })
  t.after(() => {
    api?.dispose()
    for (const [key, descriptor] of Object.entries(original)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  })
  const { createBattleScene } = makeModule({ ...THREE, WebGLRenderer: Renderer }, createCultivatorModel, battleImpact)
  api = createBattleScene({ clientWidth: width, clientHeight: height, appendChild() {} }, {
    labels: value => labels.push(value), select() {}, failure() { failures++; api?.dispose() },
  })
  return {
    ...api, renderer, canvas, document, labels,
    get pending() { return frames.size }, get failures() { return failures }, get disconnected() { return disconnected },
    draw(delta = 16) {
      now += delta
      const [id, callback] = frames.entries().next().value ?? []
      assert.ok(callback, 'a scene frame is scheduled')
      frames.delete(id); callback(now)
    },
  }
}
const unit = (side, slot) => ({ id: `${side}-${slot}`, name: `${side}-${slot}`, template_id: slot % 2 ? 'guanyu' : 'libai', side, slot, hp: 100, max_hp: 100 })
const state = (units, extra = {}) => ({ units, event: null, phase: 'idle', playing: false, reduced: false, ...extra })
function ownedResources(scene) {
  const resources = new Set()
  scene.traverse(object => {
    if (!object.isMesh) return
    resources.add(object.geometry)
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) resources.add(material)
  })
  return [...resources]
}

test('real six-versus-six geometry and labels fit the desktop and mobile battle cameras', async t => {
  for (const [width, height] of [[980, 350], [390, 290]]) await t.test(`${width}x${height}`, child => {
    const view = fixture(child, { width, height })
    const units = ['ally', 'enemy'].flatMap(side => Array.from({ length: 6 }, (_, slot) => unit(side, slot)))
    view.update(state(units)); view.draw()
    const { scene, camera } = view.renderer
    for (const model of scene.children.filter(object => object.userData.unitId)) {
      const box = new THREE.Box3().setFromObject(model)
      for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
        const projected = new THREE.Vector3(x, y, z).project(camera)
        assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1, `${model.userData.unitId} remains inside the camera`)
      }
    }
    assert.equal(view.labels.at(-1).filter(label => label.visible).length, 12)
    assert.equal(view.pending, 0, 'a static result does not keep a render loop')
  })
})

test('disposing cancels frames and releases model, arena and effect resources once', t => {
  const view = fixture(t)
  const units = [unit('ally', 0), unit('enemy', 0)]
  const event = { actor_id: units[0].id, vfx: 'strike', effects: [{ target_id: units[1].id, kind: 'damage', amount: 7, absorbed: 0 }] }
  const before = structuredClone(units)
  view.update(state(units, { event, phase: 'contact', playing: true })); view.draw()
  const counts = ownedResources(view.renderer.scene).map(resource => {
    let count = 0; resource.addEventListener('dispose', () => count++); return () => count
  })
  assert.equal(view.pending, 1)
  view.dispose(); view.dispose()
  assert.ok(counts.every(count => count() === 1), 'shared geometries and materials are disposed exactly once')
  assert.equal(view.pending, 0)
  assert.equal(view.disconnected, 1)
  assert.equal(view.renderer.disposals, 1)
  assert.equal(view.renderer.contextLosses, 1)
  assert.equal(view.canvas.removed, true)
  assert.deepEqual(units, before, 'rendering does not rewrite the recorded unit state')
})

test('an asynchronous renderer failure triggers fallback and releases the scene', t => {
  const view = fixture(t, { renderError: true })
  view.update(state([unit('ally', 0)]))
  assert.doesNotThrow(() => view.draw())
  assert.equal(view.failures, 1)
  assert.equal(view.pending, 0)
  assert.equal(view.disconnected, 1)
  assert.equal(view.renderer.disposals, 1)
  assert.equal(view.canvas.removed, true)
  view.update(state([unit('enemy', 0)]))
  view.document.dispatchEvent(new Event('visibilitychange'))
  assert.equal(view.pending, 0, 'a failed scene cannot restart when props or visibility change')
})
