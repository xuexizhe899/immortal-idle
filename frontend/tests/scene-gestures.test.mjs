import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/rendering/hd2d/sceneGestures.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { SceneGestures } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

test('an unmoved pointer and small touch jitter remain building taps', () => {
  const gestures = new SceneGestures()
  gestures.start(1, 20, 30)
  assert.equal(gestures.end(1), true)

  gestures.start(2, 20, 30)
  gestures.move(2, 23, 34)
  assert.equal(gestures.end(2), true)

  gestures.start(3, 20, 30)
  gestures.move(3, 26, 30)
  assert.equal(gestures.end(3), true)
})

test('small consecutive moves cross the drag threshold and returning to the origin cannot become a tap', () => {
  const gestures = new SceneGestures()
  gestures.start(1, 40, 50)
  assert.deepEqual(gestures.move(1, 42, 50), { dx: 2, dy: 0, scale: 1 })
  assert.deepEqual(gestures.move(1, 44, 50), { dx: 2, dy: 0, scale: 1 })
  assert.deepEqual(gestures.move(1, 47, 50), { dx: 3, dy: 0, scale: 1 })
  gestures.move(1, 40, 50)

  assert.equal(gestures.end(1), false)
})

test('two fingers report midpoint translation and proportional pinch zoom', () => {
  const gestures = new SceneGestures()
  gestures.start(1, 0, 0)
  gestures.start(2, 10, 0)
  const first = gestures.move(2, 14, 4)
  assert.equal(first.dx, 2)
  assert.equal(first.dy, 2)
  assert.ok(Math.abs(first.scale - Math.hypot(14, 4) / 10) < 1e-12)

  const second = gestures.move(1, 4, 4)
  assert.equal(first.dx + second.dx, 4)
  assert.equal(first.dy + second.dy, 4)
  assert.ok(Math.abs(first.scale * second.scale - 1) < 1e-12)
  assert.equal(gestures.end(1), false)
  assert.equal(gestures.end(2), false)
})

test('lifting one finger after a pinch keeps the remaining drag from opening a building', () => {
  const gestures = new SceneGestures()
  gestures.start(1, 10, 10)
  gestures.start(2, 20, 10)
  gestures.move(2, 30, 10)
  assert.equal(gestures.end(1), false)
  assert.deepEqual(gestures.move(2, 33, 12), { dx: 3, dy: 2, scale: 1 })
  assert.equal(gestures.end(2), false)

  gestures.start(3, 33, 12)
  assert.equal(gestures.end(3), true)
})

test('two fingers without movement still suppress taps in either lift order', () => {
  for (const first of [1, 2]) {
    const gestures = new SceneGestures()
    gestures.start(1, 10, 10)
    gestures.start(2, 20, 10)
    assert.equal(gestures.end(first), false)
    assert.equal(gestures.end(first === 1 ? 2 : 1), false)
  }
})

test('cancel clears active touches, suppresses their later events, and allows a fresh tap', () => {
  const gestures = new SceneGestures()
  gestures.start(1, 10, 10)
  gestures.start(2, 20, 10)
  gestures.cancel()

  assert.equal(gestures.move(1, 12, 10), null)
  assert.equal(gestures.end(1), false)
  assert.equal(gestures.end(2), false)
  assert.equal(gestures.move(99, 0, 0), null)
  assert.equal(gestures.end(99), false)
  gestures.start(3, 30, 30)
  assert.equal(gestures.end(3), true)
})
