import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { Comment, compile, computed, createSSRApp, effectScope, h, markRaw, nextTick, reactive, ref, watch } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const compilerOptions = { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 }
async function moduleUrl(path, imports = {}) {
  let output = ts.transpileModule(await readFile(new URL(path, import.meta.url), 'utf8'), { compilerOptions }).outputText
  for (const [from, to] of Object.entries(imports)) output = output.replaceAll(`'${from}'`, `'${to}'`)
  return `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
}
const formatUrl = await moduleUrl('../src/shared/format.ts')
const textUrl = await moduleUrl('../src/presentation/gameText.ts', { '../shared/format': formatUrl })
const bindings = {
  computed, nextTick, ref, watch,
  ...await import(formatUrl), ...await import(textUrl),
  ...await import(await moduleUrl('../src/presentation/equipment.ts', { '../shared/format': formatUrl, './gameText': textUrl })),
}
async function component(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\r?\n/gm, '')
  const syntax = ts.createSourceFile(path, script, ts.ScriptTarget.ES2022, true)
  const names = syntax.statements.flatMap(statement => ts.isVariableStatement(statement)
    ? statement.declarationList.declarations.map(item => item.name.getText(syntax))
    : ts.isFunctionDeclaration(statement) ? [statement.name.text] : [])
  return {
    setup: new Function(...Object.keys(bindings), 'useGameStore', 'defineProps', 'defineEmits',
      `${ts.transpileModule(script, { compilerOptions }).outputText}\nreturn { ${names.join(', ')} }`),
    render: compile(source.match(/<template>([\s\S]*)<\/template>/)[1], { prefixIdentifiers: true }),
  }
}
const craftComponent = await component('../src/views/CraftPanel.vue')
const equipmentComponent = await component('../src/views/EquipmentPanel.vue')
const discipleComponent = await component('../src/components/game/DiscipleEquipment.vue')
function gear(extra = {}) {
  return {
    id: 'gear-1', name: '青竹剑', slot: 'weapon', tier: 1, level: 1, max_level: 3,
    stats: { atk: .1 }, upgrade_stats: { atk: .15 }, upgrade_costs: { lian_qi_jing_cui: 4 },
    reforge_costs: { lian_qi_jing_cui: 2 }, smelt_returns: { lian_qi_jing_cui: 8 },
    affix: 'spd', affix_value: .03, affix_grade: 1, pending_affix: null,
    equipped_by: null, locked: false, source: 'drop', upgradeable: true,
    upgrade_reason: '', reforge_reason: '', resolve_reason: '', smelt_reason: '',
    equip_reason: '', unequip_reason: '', lock_reason: '', ...extra,
  }
}
function disciple(id = 'disciple-1') {
  return { id, template_id: id, gear_slots: {}, equipment: [], busy: false, injury_stacks: 1, pill_grades: {}, pill_uses: {} }
}
function weapon(extra = {}) {
  return { id: 'special-1', template_id: 'disciple-1', name: '青竹专武', template_name: '青竹', owned: false, level: 0, max_level: 3,
    stats: { atk: .2 }, upgrade_stats: { atk: .3 }, inputs: { wood: 5 }, upgrade_inputs: { wood: 10 },
    unlock_floor: 1, unlock_level: 1, equipped_by: null, in_inventory: false,
    reason: '', upgrade_reason: '', craftable: true, upgradeable: true, ...extra }
}
function setup(component, props = {}, extra = {}) {
  const calls = [], events = []
  const behavior = { previewRecipes: async grade => ({ recipes: [{ id: 'pill', kind: 'pill', name: '养元丹', grade, stock: 2, max_quantity: 10, reason: '', inputs: { wood: 2 }, effects: [{ stat: 'atk', mode: 'add_pct', value: .1 }] }] }) }
  const store = reactive({
    slotId: 1, revision: 1, busy: false,
    state: { facility_levels: { alchemy: 3, forge: 3 }, inventory: { wood: 20, 'pill:g2': 2, lian_qi_jing_cui: 20 }, active_run: null },
    catalog: { recipes: { pill: { name: '养元丹', kind: 'pill', max_uses: 3 } }, materials: { wood: '灵木' }, weapons: {}, disciples: { 'disciple-1': { name: '青竹' }, 'disciple-2': { name: '白鹤' } } },
    disciples: [disciple(), disciple('disciple-2')], gearList: [gear(), gear({ id: 'gear-2', name: '白鹤剑' })],
    gearRules: { material: 'lian_qi_jing_cui', material_name: '炼器精粹' }, weapons: [weapon()],
    loadEquipment: async () => {}, loadWeapons: async () => {},
    previewRecipes: grade => behavior.previewRecipes(grade),
    productionDestination: () => ({ label: '前往生产' }), planProduction: () => 'duty',
    ...extra,
  })
  for (const command of ['craft', 'usePill', 'craftWeapon', 'upgradeWeapon', 'equipmentAction', 'equipWeapon', 'unequipWeapon']) {
    store[command] = async (...args) => { calls.push([command, ...args]) }
  }
  const reactiveProps = reactive({ readOnly: false, ...props })
  const scope = effectScope()
  const view = scope.run(() => component.setup(...Object.values(bindings), () => store, () => reactiveProps, () => (...args) => events.push(args)))
  return { ...view, store, props: reactiveProps, component, behavior, calls, events, stop: () => scope.stop() }
}
async function flushView() { await nextTick(); await nextTick(); await nextTick() }
function flatten(node) {
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!node || typeof node !== 'object') return []
  return [node, ...(Array.isArray(node.children) ? flatten(node.children) : [])]
}
function textOf(node) {
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (!node || typeof node !== 'object') return String(node ?? '')
  if (node.type === Comment) return ''
  return typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? node.children.map(textOf).join('') : ''
}
async function renderView(view) {
  const roots = []
  const app = createSSRApp({ setup: () => ({ ...bindings, ...view, ...view.props }), render(...args) {
    const node = view.component.render.apply(this, args); roots.push(node); return node
  } })
  app.component('PanelModal', { props: ['title', 'subtitle'], setup(props, { slots }) { return () => {
    const children = slots.default?.() ?? []; roots.push(children)
    return h('section', { role: 'dialog', 'aria-label': props.title }, children)
  } } })
  for (const name of ['GearIcon', 'ItemIcon', 'EquipmentPanel']) app.component(name, { render: () => h('div', { 'data-component': name }) })
  return { html: await renderToString(app), nodes: roots.flatMap(flatten) }
}
function button(rendered, label) {
  const node = rendered.nodes.find(node => node.type === 'button' && textOf(node).trim().replace(/\s+/g, ' ') === label)
  assert.ok(node, `button ${label} exists`)
  return node
}
async function click(view, label) {
  const node = button(await renderView(view), label)
  assert.ok(!node.props.disabled, `button ${label} is enabled`)
  await node.props.onClick(); await flushView()
}

test('alchemy shows one section, opens recipes explicitly and preserves grade, quantity and material destination', async t => {
  const view = setup(craftComponent, { kind: 'pill' }); t.after(view.stop)
  await flushView()
  let rendered = await renderView(view)
  assert.doesNotMatch(rendered.html, /role="dialog"|class="use-section"|class="inventory-details"/)
  assert.match(rendered.html, /选择配方/)
  view.grade.value = 2; await flushView()
  view.openRecipe('pill'); await flushView()
  view.quantity.value = 3
  await click(view, '炼制 3 颗')
  assert.deepEqual(view.calls, [['craft', 'pill', 3, 2]])
  rendered = await renderView(view)
  assert.match(rendered.html, /role="dialog"/)
  assert.match(rendered.html, /20 \/ 6/)
  view.findMaterial('wood'); await flushView()
  assert.equal(view.recipeOpen.value, false)
  assert.deepEqual(view.events, [['open', 'duty']])
  assert.equal(view.selectedId.value, 'pill')
})

test('pill use and inventory do not accumulate with recipes; use keeps the selected item and disciple', async t => {
  const view = setup(craftComponent, { kind: 'pill' }); t.after(view.stop); await flushView()
  view.openRecipe('pill'); await flushView()
  await click(view, '服用丹药')
  assert.equal(view.recipeOpen.value, false)
  let rendered = await renderView(view)
  assert.match(rendered.html, /class="use-section"/)
  assert.doesNotMatch(rendered.html, /aria-label="选择配方"|class="inventory-details"/)
  view.useTarget.value = 'disciple-2'; await flushView()
  await click(view, '为所选弟子服用')
  assert.deepEqual(view.calls, [['usePill', 'pill:g2', 'disciple-2']])
  await click(view, '宗门行囊')
  rendered = await renderView(view)
  assert.match(rendered.html, /class="inventory-details"/)
  assert.doesNotMatch(rendered.html, /class="use-section"|aria-label="选择配方"/)
  view.store.slotId = 2; await flushView()
  assert.equal(view.section.value, 'primary')
  assert.equal(view.useTarget.value, '')
})

test('recipe refresh retains an open valid recipe, discards late grade results and closes missing recipes', async t => {
  const view = setup(craftComponent, { kind: 'pill' }); t.after(view.stop); await flushView()
  view.openRecipe('pill'); await flushView()
  view.store.revision += 1; await flushView()
  assert.equal(view.recipeOpen.value, true)
  const pending = []
  view.behavior.previewRecipes = grade => new Promise(resolve => pending.push({ grade, resolve }))
  view.grade.value = 2; await flushView()
  assert.equal(view.recipeOpen.value, false)
  view.grade.value = 3; await flushView()
  pending[1].resolve({ recipes: [{ id: 'pill', kind: 'pill', grade: 3 }] }); await flushView()
  pending[0].resolve({ recipes: [{ id: 'old', kind: 'pill', grade: 2 }] }); await flushView()
  assert.equal(view.recipes.value[0].grade, 3)
  view.openRecipe('pill'); await flushView()
  view.behavior.previewRecipes = async () => ({ recipes: [] })
  view.store.revision += 1; await flushView()
  assert.equal(view.recipeOpen.value, false)
})

test('alchemy keeps quantity, read-only and busy restrictions inside the recipe dialog', async t => {
  const view = setup(craftComponent, { kind: 'pill', readOnly: true }); t.after(view.stop); await flushView()
  view.openRecipe('pill'); await flushView()
  assert.equal(button(await renderView(view), '炼制 1 颗').props.disabled, true)
  await view.craft(); assert.deepEqual(view.calls, [])
  view.props.readOnly = false; view.quantity.value = 11
  assert.equal(button(await renderView(view), '炼制 11 颗').props.disabled, true)
  await view.craft(); assert.deepEqual(view.calls, [])
  view.quantity.value = 1; view.store.busy = true
  assert.equal(button(await renderView(view), '炼制 1 颗').props.disabled, true)
})

test('forge separates ordinary equipment, compact exclusive-weapon choices and inventory without changing commands', async t => {
  const view = setup(craftComponent, { kind: 'weapon' }); t.after(view.stop); await flushView()
  let rendered = await renderView(view)
  assert.match(rendered.html, /data-component="EquipmentPanel"/)
  assert.doesNotMatch(rendered.html, /weapon-grid|role="dialog"/)
  await click(view, '弟子专武')
  rendered = await renderView(view)
  assert.match(rendered.html, /weapon-grid/)
  assert.doesNotMatch(rendered.html, /data-component="EquipmentPanel"|weapon-materials/)
  view.openWeapon('special-1'); await flushView()
  await click(view, '锻造专武')
  view.store.weapons[0].owned = true; view.store.weapons[0].level = 1; await flushView()
  await click(view, '升级专武')
  assert.deepEqual(view.calls, [['craftWeapon', 'special-1'], ['upgradeWeapon', 'special-1']])
  view.props.readOnly = true; await flushView()
  assert.equal(button(await renderView(view), '升级专武').props.disabled, true)
  view.store.slotId = 2; await flushView()
  assert.equal(view.selectedWeapon.value, undefined)
})

test('equipment details open on demand, preserve filters when closed and close when filtered out or switching saves', async t => {
  const view = setup(equipmentComponent); t.after(view.stop); await flushView()
  assert.equal(view.detailOpen.value, false)
  assert.doesNotMatch((await renderView(view)).html, /gear-detail|role="dialog"/)
  view.openEquipment('gear-2'); await flushView()
  assert.match((await renderView(view)).html, /role="dialog"/)
  view.search.value = '白鹤'; await flushView()
  view.confirmSmelt.value = true
  view.closeEquipment(); await flushView()
  assert.equal(view.confirmSmelt.value, false)
  assert.equal(view.search.value, '白鹤')
  assert.equal(view.selectedId.value, 'gear-2')
  view.store.revision += 1; await flushView()
  assert.equal(view.detailOpen.value, false)
  view.openEquipment('gear-2'); view.search.value = '青竹'; await flushView()
  assert.equal(view.detailOpen.value, false)
  view.openEquipment('gear-1'); await flushView()
  view.store.slotId = 2; await flushView()
  assert.equal(view.detailOpen.value, false)
  assert.equal(view.selectedId.value, '')
})

test('equipment upgrade, locking, reforge resolution and confirmed smelting keep their original command parameters', async t => {
  const view = setup(equipmentComponent); t.after(view.stop); await flushView()
  view.openEquipment('gear-1'); await flushView()
  await click(view, '锁定装备')
  await click(view, '强化这件装备')
  await click(view, '洗练'); await click(view, '消耗材料，生成洗练结果')
  view.store.gearList[0].pending_affix = { stat: 'hp', value: .06, grade: 2 }; await flushView()
  await click(view, '保留原属性'); await click(view, '采用新属性')
  view.store.gearList[0].pending_affix = null; await flushView()
  await click(view, '熔炼')
  await view.smelt()
  assert.equal(view.calls.length, 5, 'an unconfirmed smelt cannot issue a command')
  await click(view, '熔炼这件装备')
  assert.equal(view.confirmSmelt.value, true)
  await click(view, '确认熔炼')
  assert.deepEqual(view.calls, [
    ['equipmentAction', 'lock', 'gear-1', { locked: true }], ['equipmentAction', 'upgrade', 'gear-1'],
    ['equipmentAction', 'reforge', 'gear-1'], ['equipmentAction', 'resolve', 'gear-1', { keep: true }],
    ['equipmentAction', 'resolve', 'gear-1', { keep: false }], ['equipmentAction', 'smelt', 'gear-1'],
  ])
  assert.equal(view.confirmSmelt.value, false)
})

test('equipment modal resets scroll on section changes and keeps read-only and busy actions disabled', async t => {
  const view = setup(equipmentComponent, { readOnly: true }); t.after(view.stop); await flushView()
  view.openEquipment('gear-1'); await flushView()
  assert.equal(button(await renderView(view), '强化这件装备').props.disabled, true)
  const resets = []
  view.detailModal.value = markRaw({ resetScroll: () => resets.push(true) })
  view.detailTab.value = 'smelt'; await flushView()
  assert.deepEqual(resets, [true])
  assert.equal(button(await renderView(view), '熔炼这件装备').props.disabled, true)
  view.confirmSmelt.value = true; await view.smelt()
  assert.deepEqual(view.calls, [])
  view.props.readOnly = false; view.store.busy = true
  assert.equal(button(await renderView(view), '确认熔炼').props.disabled, true)
})

test('disciple equipment uses a slot dialog and mutually exclusive ordinary and special views', async t => {
  const view = setup(discipleComponent, { disciple: disciple() }); t.after(view.stop); await flushView()
  assert.doesNotMatch((await renderView(view)).html, /role="dialog"|candidate-detail/)
  view.openSlot('weapon'); await flushView()
  let rendered = await renderView(view)
  assert.match(rendered.html, /role="dialog"/)
  assert.match(rendered.html, /同部位装备增益对比/)
  assert.doesNotMatch(rendered.html, /class="special-weapon"/)
  await click(view, '穿戴这件装备')
  assert.deepEqual(view.calls, [['equipmentAction', 'equip', 'gear-1', { disciple_id: 'disciple-1' }]])
  await click(view, '专属武器')
  rendered = await renderView(view)
  assert.match(rendered.html, /class="special-weapon"/)
  assert.doesNotMatch(rendered.html, /candidate-detail|candidate-select/)
  view.store.weapons[0].owned = true; view.store.weapons[0].in_inventory = true; await flushView()
  await click(view, '穿戴专属武器')
  view.props.disciple.equipment = ['special-1']; await flushView()
  await click(view, '卸下专属武器')
  assert.deepEqual(view.calls.slice(1), [['equipWeapon', 'special-1', 'disciple-1'], ['unequipWeapon', 'disciple-1']])
  view.props.disciple = disciple('disciple-2'); await flushView()
  assert.equal(view.pickerOpen.value, false)
})

test('disciple modal retains transfer context and respects expedition and read-only locks', async t => {
  const view = setup(discipleComponent, { disciple: disciple() }, { gearList: [gear({ equipped_by: 'disciple-2' })] }); t.after(view.stop); await flushView()
  view.openSlot('weapon'); await flushView()
  assert.match((await renderView(view)).html, /这件装备会从白鹤转交给当前弟子/)
  view.props.readOnly = true
  assert.equal(button(await renderView(view), '转交并穿戴').props.disabled, true)
  view.props.readOnly = false; view.store.state.active_run = { party: ['disciple-1'] }
  assert.equal(button(await renderView(view), '转交并穿戴').props.disabled, true)
  view.store.state.active_run = null; view.store.busy = true
  assert.equal(button(await renderView(view), '转交并穿戴').props.disabled, true)
  view.store.slotId = 2; await flushView()
  assert.equal(view.pickerOpen.value, false)
  assert.deepEqual(view.calls, [])
})
