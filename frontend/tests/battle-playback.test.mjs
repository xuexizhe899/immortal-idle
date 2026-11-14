import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/rendering/battlePlayback.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { affixSourceText, battleUnitsAt, effectLabel, playbackIndices } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

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

test('battle details show the recorded attacker and defender affixes without changing floating damage', () => {
  const names = new Map([['ally', '关羽'], ['enemy:0', '石甲灵卫']])
  const effect = { kind: 'damage', target_id: 'enemy:0', amount: 7, absorbed: 3, affixes: [
    { id: 'po_jun', name: '破军', unit_id: 'ally', stat: 'damage', value: .05 },
    { id: 'pan_shi', name: '磐石', unit_id: 'enemy:0', stat: 'taken_damage', value: .06 },
  ] }
  const before = structuredClone(effect)

  assert.equal(effectLabel(effect), '−7 · 盾挡 3')
  assert.equal(effectLabel(effect, names), '−7 · 盾挡 3 · 道法修正：关羽·破军 伤害 +5%；石甲灵卫·磐石 减伤 +6%')
  assert.deepEqual(effect, before)
})

test('healing and entry attributes use only recorded contributions, including their capped value', () => {
  const names = new Map([['ally', '诸葛亮']])
  assert.equal(effectLabel({ kind: 'heal', amount: 0, affixes: [
    { id: 'hui_chun', name: '回春', unit_id: 'ally', stat: 'healing', value: .075 },
  ] }, names), '气血 +0 · 道法修正：诸葛亮·回春 治疗 +7.5%')
  assert.equal(affixSourceText([
    { id: 'lian_feng', name: '连锋', unit_id: 'ally', stat: 'atk', value: .04 },
    { id: 'lian_feng', name: '连锋', unit_id: 'ally', stat: 'spd', value: .03 },
  ], names), '诸葛亮·连锋 攻击 +4%；诸葛亮·连锋 身法 +3%')
})

test('legacy battle events without affix sources keep their original descriptions', () => {
  const names = new Map([['ally', '关羽']])
  assert.equal(effectLabel({ kind: 'damage', amount: 8, absorbed: 0 }, names), '−8')
  assert.equal(effectLabel({ kind: 'shield', amount: 4, affixes: [] }, names), '护盾 +4')
  assert.equal(affixSourceText(undefined, names), '')
})

test('direct-result mode schedules no actions and keeps the exact final snapshot and complete log available', () => {
  const result = {
    initial_units: [{ id: 'ally', hp: 30, shield: 0 }],
    events: [{ sequence: 1, units: [{ id: 'ally', hp: 22, shield: 0 }] }],
    final_units: [{ id: 'ally', hp: 22, shield: 0 }],
    loot: { cultivation: 12.34 },
  }
  const before = structuredClone(result)

  assert.deepEqual(playbackIndices(result.events, 'result'), [])
  assert.deepEqual(playbackIndices([], 'result'), [])
  assert.strictEqual(battleUnitsAt(result, result.events.length), result.final_units)
  assert.deepEqual(playbackIndices(result.events, 'all'), [0], 'the original log remains replayable when switching back')
  assert.deepEqual(result, before)
})
