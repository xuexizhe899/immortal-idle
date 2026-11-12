import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/rendering/battlePlayback.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { battleUnitsAt, effectLabel, playbackIndices } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

test('key playback stays bounded for a 240-action battle while preserving chronological order and final action', () => {
  const events = Array.from({ length: 240 }, (_, index) => ({ sequence: index + 1, skill_id: index % 3 ? 'basic_attack' : 'moonlight', bonds: index === 207 ? ['benyue'] : [] }))
  const indices = playbackIndices(events, 'key')
  assert.ok(indices.length <= 10)
  assert.equal(indices[0], 0)
  assert.equal(indices.at(-1), 239)
  assert.ok(indices.includes(207), 'a later bond trigger should remain visible in key playback')
  assert.deepEqual([...indices].sort((a, b) => a - b), indices)
  assert.equal(new Set(indices).size, indices.length)
  assert.deepEqual(playbackIndices(events, 'all'), Array.from({ length: 240 }, (_, index) => index))
})

test('replay and skipping use exact server snapshots without recomputing health or rewards', () => {
  const result = { initial_units: [{ id: 'ally', hp: 31, shield: 7 }], events: [{ units: [{ id: 'ally', hp: 31, shield: 2 }] }, { units: [{ id: 'ally', hp: 38, shield: 2 }] }], final_units: [{ id: 'ally', hp: 38, shield: 0 }] }
  const before = structuredClone(result)
  assert.strictEqual(battleUnitsAt(result, -1), result.initial_units)
  assert.strictEqual(battleUnitsAt(result, 0), result.events[0].units)
  assert.strictEqual(battleUnitsAt(result, 1), result.events[1].units)
  assert.strictEqual(battleUnitsAt(result, 2), result.final_units)
  assert.strictEqual(battleUnitsAt(result, 1000), result.final_units)
  assert.strictEqual(battleUnitsAt(result, -1), result.initial_units)
  assert.deepEqual(result, before)
  assert.equal(effectLabel({ kind: 'damage', amount: 0, absorbed: 5 }), '未失血 · 盾挡 5')
  assert.equal(effectLabel({ kind: 'heal', amount: 7 }), '气血 +7')
})
