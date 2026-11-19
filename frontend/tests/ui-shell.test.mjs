import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { computed, effectScope, ref, watch } from 'vue'
import { parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { harness, json } from './store-harness.mjs'

const source = await readFile(new URL('../src/App.vue', import.meta.url), 'utf8')
const script = parse(source).descriptor.scriptSetup.content.replace(/^import .*\r?\n/gm, '')
const code = ts.transpileModule(script, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText

test('dismissing an uncertain request error never presents an unconfirmed old save as synchronized', async t => {
  const session = harness()
  t.after(() => session.cleanup())
  await session.store.bootstrap()
  const scope = effectScope()
  t.after(() => scope.stop())
  const view = scope.run(() => new Function('computed', 'ref', 'watch', 'onMounted', 'useGameStore',
    `${code}\nreturn { saveStatus }`)(computed, ref, watch, () => {}, () => session.store))
  const original = session.store.revision
  session.respond('POST', '/saves/1/duty/assign', () => { throw new TypeError('connection lost') })
  session.respond('GET', '/saves/1', () => json({ detail: '暂时无法读取' }, 503))
  await session.store.assignDuty('alpha')
  assert.match(session.store.error, /尚未确认最新进度/)
  assert.match(view.saveStatus.value, /待确认/)
  session.store.clearError()
  assert.equal(session.store.revision, original)
  assert.equal(session.count('POST', '/saves/1/duty/assign'), 1)
  assert.doesNotMatch(view.saveStatus.value, /已同步|已保存|已确认/)
})
