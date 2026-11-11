import assert from 'node:assert/strict'
import { access, readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadTypeScript(relativePath) {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
}

const { ITEM_ICON_IDS, itemIconPath } = await loadTypeScript('../src/components/itemIcons.ts')
const manifest = JSON.parse(await readFile(new URL('../public/assets/items/index.json', import.meta.url), 'utf8'))

test('item registry covers every generated icon and file', async () => {
  const ids = manifest.items.map(item => item.id)
  assert.equal(ids.length, 18)
  assert.deepEqual([...ITEM_ICON_IDS].sort(), [...ids].sort())
  for (const item of manifest.items) {
    await access(new URL(`../public/assets/items/${item.file}`, import.meta.url))
  }
})

test('unknown or unsafe ids never produce an image request', () => {
  assert.equal(itemIconPath('han_tie'), '/assets/items/han_tie.svg')
  assert.equal(itemIconPath('qing_feng_jian'), '/assets/items/qing_feng_jian.svg')
  assert.equal(itemIconPath('unknown_item'), '')
  assert.equal(itemIconPath('../secret'), '')
  assert.equal(itemIconPath('han_tie/../../secret'), '')
  assert.equal(itemIconPath(''), '')
  assert.equal(itemIconPath(null), '')
  assert.equal(itemIconPath(undefined), '')
})
