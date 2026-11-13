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
const { snapshotAffixes } = await import(await moduleUrl('../src/presentation/gameText.ts', {
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
