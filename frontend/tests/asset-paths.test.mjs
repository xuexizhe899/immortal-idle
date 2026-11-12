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

const { ITEM_ICON_IDS, itemIconPath, characterImage, discipleImage, snapshotDiscipleImage, sceneImage } = await loadTypeScript('../src/presentation/assetPaths.ts')
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

test('character keys and scene urls resolve to existing local assets without duplicate extensions', async () => {
  assert.equal(characterImage('trial-v03/zhugeliang'), '/assets/trial-v03/zhugeliang.png')
  assert.equal(characterImage('trial-v03/zhugeliang.png'), '/assets/trial-v03/zhugeliang.png')
  assert.equal(characterImage('/assets/trial-v03/guanyu.png'), '/assets/trial-v03/guanyu.png')
  assert.equal(characterImage(''), '')
  assert.equal(characterImage(undefined), '')
  assert.equal(sceneImage('/assets/city-v03/scene_city_complete.png'), '/assets/city-v03/scene_city_complete.png')
  assert.equal(sceneImage('trial-v03/scene_tower_trial.png'), '/assets/trial-v03/scene_tower_trial.png')
  assert.equal(sceneImage(null), '')
  await access(new URL(`../public${characterImage('trial-v03/zhugeliang')}`, import.meta.url))
  await access(new URL(`../public${sceneImage('/assets/city-v03/scene_city_complete.png')}`, import.meta.url))
})

test('a fixed expedition snapshot keeps its portrait instead of the current catalog', () => {
  const catalog = { disciples: { guanyu: { asset_id: 'trial-v03/guanyu' } } }
  assert.equal(snapshotDiscipleImage('trial-v03/zhugeliang', 'guanyu', catalog), '/assets/trial-v03/zhugeliang.png')
  assert.equal(snapshotDiscipleImage('', 'guanyu', catalog), '/assets/trial-v03/guanyu.png')
  assert.equal(snapshotDiscipleImage(undefined, 'guanyu', null), '/assets/guanyu.png')
  assert.equal(discipleImage('guanyu', catalog), '/assets/trial-v03/guanyu.png')
})