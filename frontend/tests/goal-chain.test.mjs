import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadHelper(name) {
  const source = await readFile(new URL(`../src/presentation/${name}.ts`, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
}

const { materialSources } = await loadHelper('materialSources')
const { pickNextAction } = await loadHelper('nextAction')

const catalog = {
  materials: { ling_cao: '灵草', ling_mu: '灵木', chi_tong: '赤铜', gong_fa_qi_pei: '攻伐器胚' },
  production: { materials: { ling_cao: .5, ling_mu: .5, chi_tong: .5, gong_fa_qi_pei: 0 } },
  disciples: {
    huatuo: { name: '华佗', production_specialty: 'ling_cao' },
    libai: { name: '李白', production_specialty: 'gong_fa_qi_pei' },
  },
  mode: { rewards: { battle: { ling_cao: 1 }, boss: { ling_cao: 5 } } },
  sect_styles: [
    { name: '剑修', suffix: '剑宗', retrial_reward: { chi_tong: 4, spirit_stone: 10 } },
    { name: '丹修', suffix: '丹宗', retrial_reward: { ling_mu: 8, spirit_stone: 11 } },
  ],
}
const state = {
  facility_levels: { training: 2 },
  sects: [
    { id: 'sect_1', name: '云岚剑宗', style: '剑修', level: 1, material_id: 'han_tie', special_material_id: 'gong_fa_qi_pei', conquered: true, loot: { chi_tong: 8, spirit_stone: 30 } },
    { id: 'sect_2', name: '赤霞丹宗', style: '丹修', level: 1, material_id: 'ling_cao', special_material_id: 'po_jing_ling_cai', conquered: false, loot: { ling_cao: 4, ling_mu: 8, spirit_stone: 30 } },
  ],
}
const world = {
  regions: [{ id: 1, name: '云岚下界', unlocked: true, tower_rewards: catalog.mode.rewards, nodes: state.sects.map(sect => ({
    kind: 'sect', sect_id: sect.id, locked: false,
    retrial_rewards: catalog.sect_styles.find(style => style.name === sect.style).retrial_reward,
  })) }],
}

test('source matrix covers every material and separates rates from one-time rewards', () => {
  const matrix = materialSources(catalog, state, world)
  assert.deepEqual(Object.keys(matrix).sort(), Object.keys(catalog.materials).sort())
  const lingcao = matrix.ling_cao
  assert.equal(lingcao.find(source => source.kind === 'idle').rate, .5)
  const duty = lingcao.find(source => source.kind === 'duty')
  assert.equal(duty.rate, .625)
  assert.ok(duty.detail.includes('华佗'))
  assert.ok(lingcao.find(source => source.kind === 'tower').detail.includes('普通 +1'))
  assert.ok(lingcao.find(source => source.kind === 'tower').detail.includes('首领 +5'))
  assert.equal(lingcao.find(source => source.kind === 'garrison').available, false)
  assert.equal(lingcao.find(source => source.kind === 'conquest').available, true)
})

test('special materials have no idle or duty rate but show garrison and retrial gates', () => {
  const matrix = materialSources(catalog, state, world)
  const special = matrix.gong_fa_qi_pei
  assert.ok(!special.some(source => source.kind === 'idle' || source.kind === 'duty'))
  const garrison = special.find(source => source.kind === 'garrison')
  assert.equal(garrison.rate, undefined, 'garrison output must come from the actual server production view')
  assert.equal(garrison.available, true)
  const retrial = matrix.chi_tong.find(source => source.kind === 'retrial')
  assert.equal(retrial.available, true)
  assert.equal(matrix.chi_tong.find(source => source.kind === 'conquest').available, false)
  assert.equal(matrix.ling_mu.find(source => source.kind === 'retrial').available, false)
  assert.deepEqual(materialSources(null, state), {})
})

test('next action prefers upgradeable, then missing cost, then craftable, else null', () => {
  const held = id => ({ ling_mu: 3, spirit_stone: 100 }[id] ?? 0)
  const nameOf = id => ({ ling_mu: '灵木' }[id] ?? id)
  const facility = { id: 'hall', name: '宗门主殿', level: 1, max_level: 3, upgradeable: false, costs: { ling_mu: 8, spirit_stone: 20 } }
  assert.deepEqual(
    pickNextAction([{ ...facility, upgradeable: true }], [], held, nameOf),
    { label: '可升级宗门主殿', panel: 'sect' },
  )
  assert.deepEqual(
    pickNextAction([facility], [], held, nameOf),
    { label: '升级宗门主殿缺灵木', panel: 'sect' },
  )
  assert.deepEqual(
    pickNextAction([{ ...facility, level: 3 }], [{ name: '疗伤丹', kind: 'pill', max_quantity: 2 }], held, nameOf),
    { label: '可炼疗伤丹', panel: 'alchemy' },
  )
  assert.equal(
    pickNextAction([{ ...facility, level: 3 }], [{ name: '青锋剑', kind: 'artifact', max_quantity: 1 }], held, nameOf).panel,
    'forge',
  )
  assert.equal(pickNextAction([], [], held, nameOf), null)
})
