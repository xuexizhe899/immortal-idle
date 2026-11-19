import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function moduleUrl(path, imports = {}) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  let output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
  for (const [specifier, destination] of Object.entries(imports)) output = output.replaceAll(`from '${specifier}'`, `from ${JSON.stringify(destination)}`)
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}
const formatUrl = await moduleUrl('../src/shared/format.ts')
const gameTextUrl = await moduleUrl('../src/presentation/gameText.ts', { '../shared/format': formatUrl })
const { equipmentAffixText, equipmentComparison, equipmentPercent, equipmentSlots, equipmentStats, smeltBlockReason } = await import(await moduleUrl('../src/presentation/equipment.ts', {
  '../shared/format': formatUrl,
  './gameText': gameTextUrl,
}))

test('equipment comparison retains lost and gained attributes without changing server values', () => {
  const current = { atk: .12, hp: .05, healing: .02 }
  const candidate = { atk: .08, spd: .04 }
  const before = structuredClone({ current, candidate })
  assert.deepEqual(equipmentComparison(current, candidate), [
    { stat: 'hp', name: '气血', current: .05, candidate: 0, delta: -.05 },
    { stat: 'atk', name: '攻击', current: .12, candidate: .08, delta: -.04 },
    { stat: 'spd', name: '身法', current: 0, candidate: .04, delta: .04 },
    { stat: 'healing', name: '治疗', current: .02, candidate: 0, delta: -.02 },
  ])
  assert.deepEqual({ current, candidate }, before)
})

test('an empty slot compares with zero while unchanged server attributes stay unchanged', () => {
  assert.deepEqual(equipmentComparison({}, { shielding: .09 }), [
    { stat: 'shielding', name: '护盾', current: 0, candidate: .09, delta: .09 },
  ])
  assert.equal(equipmentComparison({ atk: .08 }, { atk: .08 })[0].delta, 0)
  assert.deepEqual(equipmentSlots, ['weapon', 'armor', 'boots', 'ring'])
})

test('gear text displays the recorded percentage and affix grade rather than rolling new values', () => {
  assert.equal(equipmentAffixText('healing', .075, 2), '治疗 +7.5% · 2 档')
  assert.equal(equipmentAffixText('', 0, 1), '无副属性')
  assert.equal(equipmentPercent(.036), '+3.6%')
  assert.equal(equipmentPercent(-.025), '-2.5%')
  assert.equal(equipmentPercent(0), '0%')
  assert.deepEqual(equipmentStats({ def: .1032 }), [{ stat: 'def', name: '防御', value: .1032, text: '+10.32%' }])
})

test('smelt confirmation remains blocked for worn, locked, pending or read-only equipment', () => {
  const item = { equipped_by: null, locked: false, pending_affix: null, smelt_reason: '' }
  assert.equal(smeltBlockReason(item), '')
  assert.equal(smeltBlockReason({ ...item, equipped_by: 'disciple:1' }), '请先卸下装备')
  assert.equal(smeltBlockReason({ ...item, locked: true }), '请先解除锁定')
  assert.equal(smeltBlockReason({ ...item, pending_affix: { stat: 'atk', value: .02, grade: 1 } }), '请先选择洗练结果')
  assert.equal(smeltBlockReason(item, true), '出征结束后可熔炼装备')
  assert.equal(smeltBlockReason({ ...item, smelt_reason: '服务端禁止本次操作' }), '服务端禁止本次操作')
  assert.deepEqual(item, { equipped_by: null, locked: false, pending_affix: null, smelt_reason: '' })
})
