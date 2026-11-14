import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function moduleUrl(path, imports = {}) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  let output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  }).outputText
  for (const [specifier, destination] of Object.entries(imports)) {
    output = output.replaceAll(`from '${specifier}'`, `from ${JSON.stringify(destination)}`)
  }
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}

const formatUrl = await moduleUrl('../src/shared/format.ts')
const { snapshotAffixes, snapshotEncounter } = await import(await moduleUrl('../src/presentation/gameText.ts', {
  '../shared/format': formatUrl,
}))

test('legacy affix snapshots describe their original effects and group without current catalog rules', () => {
  const pool = [{ id: 'hui_chun', name: '旧局回春', group: 'jianshou', effects: [
    { stat: 'hp', mode: 'add_pct', value: .04 },
    { stat: 'def', mode: 'add_flat', value: 2 },
  ] }]
  const before = structuredClone(pool)

  assert.deepEqual(snapshotAffixes(pool).hui_chun, {
    name: '旧局回春', group: 'jianshou', groupName: '坚守', description: '气血 +4%，防御 +2',
  })
  assert.deepEqual(pool, before)
})

test('current affix snapshots retain their recorded descriptions and display names', () => {
  const pool = [{ id: 'hui_chun', name: '回春', group: 'jianshou', group_name: '本局坚守',
    description: '治疗量提高 20%。', bonuses: { healing: .2 } }]

  assert.deepEqual(snapshotAffixes(pool).hui_chun, {
    name: '回春', group: 'jianshou', groupName: '本局坚守', description: '治疗量提高 20%。',
  })
})

test('an absent snapshot supplies no guessed definitions and unknown groups retain their recorded ids', () => {
  assert.deepEqual(snapshotAffixes(), {})
  assert.deepEqual(snapshotAffixes([{ id: 'old_way', group: 'old_group' }]).old_way, {
    name: 'old_way', group: 'old_group', groupName: 'old_group', description: '本局未记录道法说明',
  })
})

test('a generated node retains its exact enemies, duplicate counts and snapshot threats', () => {
  const snapshot = { route_version: 2, mode: {
    node_count: 20, encounter_variants: { battle: [['other']] },
  }, enemies: {
    archer: { name: '本局弓卫', skill: { name: '穿云箭', description: '攻击气血比例最低的敌人。' },
      passive: { name: '乘势', description: '对已被降低防御的目标伤害提高10%。' } },
    guard: { name: '石甲灵卫', skill: null, passive: null },
  } }
  const node = { kind: 'battle', enemies: ['archer', 'guard', 'archer'] }
  const before = structuredClone({ node, snapshot })

  assert.deepEqual(snapshotEncounter(node, snapshot, 17), [
    { id: 'archer', name: '本局弓卫', count: 2, threats: ['穿云箭：攻击气血比例最低的敌人。', '乘势：对已被降低防御的目标伤害提高10%。'] },
    { id: 'guard', name: '石甲灵卫', count: 1, threats: [] },
  ])
  assert.deepEqual({ node, snapshot }, before)
})

test('legacy empty node rosters follow the saved floor bands and the saved total floor count', () => {
  const snapshot = { mode: {
    node_count: 10, encounter_variants: { battle: [['early'], ['late', 'late']] },
    encounters: { battle: ['fallback'] },
  }, enemies: {} }
  const node = { kind: 'battle', enemies: [] }

  assert.deepEqual(snapshotEncounter(node, snapshot, 4).map(enemy => [enemy.id, enemy.count]), [['early', 1]])
  assert.deepEqual(snapshotEncounter(node, snapshot, 5).map(enemy => [enemy.id, enemy.count]), [['late', 2]])
  assert.deepEqual(snapshotEncounter(node, snapshot, 9).map(enemy => [enemy.id, enemy.count]), [['late', 2]])
})

test('older snapshots without variants use fixed encounters while new missing rosters are not guessed', () => {
  const snapshot = { route_version: 1, mode: { encounters: { boss: ['old_boss'] } }, enemies: {} }
  assert.deepEqual(snapshotEncounter({ kind: 'boss' }, snapshot, 19), [
    { id: 'old_boss', name: 'old_boss', count: 1, threats: [] },
  ])
  assert.deepEqual(snapshotEncounter({ kind: 'boss', enemies: [] }, { ...snapshot, route_version: 2 }, 19), [])
  assert.deepEqual(snapshotEncounter({ kind: 'battle', enemies: [] }, undefined, 0), [])
})
