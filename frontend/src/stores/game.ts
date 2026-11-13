import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  api, ApiError, type Catalog, type GameState, type SaveContent, type RunPayload,
  type RunSettleResult, type SaveSlotMeta, type SettleResult, type Production,
  type TrainingPreview, type WeaponView,
} from '../api/client'

const PREFERENCES_KEY = 'immortal-idle.preferences.v1'

function readPreferences(): { slotId?: number; parties?: Record<string, string[]> } {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? '{}')
    return value && typeof value === 'object' ? value : {}
  }
  catch { return {} }
}

export const useGameStore = defineStore('game', () => {
  const slotId = ref<number | null>(null)
  const revision = ref(0)
  const state = ref<GameState | null>(null)
  const catalog = ref<Catalog | null>(null)
  const lastRun = ref<RunSettleResult | null>(null)
  const lastSettle = ref<SettleResult | null>(null)
  const saves = ref<SaveSlotMeta[]>([])
  const party = ref<string[]>([])
  const busy = ref(false)
  const ready = ref(false)
  const operation = ref('')
  const error = ref<string | null>(null)
  const noticeText = ref<string | null>(null)
  const noticeId = ref(0)
  // 连续下发相同文案时也要重新出现并重新计时，因此单独记录提示事件序号。
  const notice = computed<string | null>({
    get: () => noticeText.value,
    set: value => {
      noticeText.value = value
      if (value) noticeId.value += 1
    },
  })
  const status = ref<SaveContent['status']>('idle')
  const production = ref<Production>({ cultivation: 0, spirit_stone: 0, stamina: 0, materials: {}, injury_recovery_multiplier: 1 })
  const disciples = computed(() => state.value?.disciples ?? [])
  const resources = computed(() => state.value?.resources)
  const battleResult = computed(() => state.value?.active_run?.last_battle ?? null)
  const training = ref<TrainingPreview | null>(null)
  const trainingFor = ref<string | null>(null)
  const trainingLoading = ref(false)
  let trainingRequest = 0
  const weapons = ref<WeaponView[]>([])
  let weaponsRequest = 0
  const run = computed<RunPayload | null>(() => state.value ? {
    revision: revision.value, state: state.value, status: status.value,
    production: production.value, run: state.value.active_run ?? null, battle_result: battleResult.value,
  } : null)

  function remember() {
    if (slotId.value === null) return
    try {
      const previous = readPreferences()
      localStorage.setItem(PREFERENCES_KEY, JSON.stringify({
        slotId: slotId.value,
        parties: { ...previous.parties, [slotId.value]: party.value },
      }))
    } catch { /* Gameplay remains available when browser storage is restricted. */ }
  }

  function cleanParty(ids = party.value) {
    const duty = new Set(state.value?.duty_slots.map(member => member.disciple_id) ?? [])
    const active = state.value?.active_run
    party.value = active ? [...active.party] : [...new Set(ids)].filter(id =>
      disciples.value.some(d => d.id === id && !d.busy) && !duty.has(id),
    ).slice(0, catalog.value?.rules.max_party ?? 6)
  }

  function applySnapshot(snapshot: SaveContent, forSlot: number) {
    if (slotId.value !== forSlot || snapshot.revision < revision.value) return
    revision.value = snapshot.revision
    state.value = snapshot.state
    status.value = snapshot.status
    production.value = snapshot.production
    cleanParty()
  }

  async function readCurrent(id: number) {
    const snapshot = await api.getSave(id)
    applySnapshot(snapshot, id)
    remember()
  }

  async function loadTraining(discipleId: string): Promise<void> {
    const id = slotId.value
    if (id === null) return
    const request = ++trainingRequest
    trainingFor.value = discipleId
    trainingLoading.value = true
    try {
      const preview = await api.training(id, discipleId)
      if (request !== trainingRequest || slotId.value !== id || trainingFor.value !== discipleId) return
      training.value = preview
    } catch (cause) {
      if (request !== trainingRequest) return
      training.value = null
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      if (request === trainingRequest) trainingLoading.value = false
    }
  }

  async function loadWeapons(silent = false): Promise<void> {
    const id = slotId.value
    if (id === null) return
    const request = ++weaponsRequest
    const requestedRevision = revision.value
    try {
      const result = await api.weapons(id)
      // 旧查询不能覆盖后续刷新或锻造、装备已经返回的专武归属。
      if (request !== weaponsRequest || slotId.value !== id || result.revision < revision.value) return
      weapons.value = result.weapons
    } catch (cause) {
      if (request !== weaponsRequest || slotId.value !== id || requestedRevision !== revision.value) return
      weapons.value = []
      if (!silent) error.value = cause instanceof Error ? cause.message : String(cause)
    }
  }

  async function guard<T>(label: string, action: () => Promise<T>): Promise<T | null> {
    if (busy.value) return null
    busy.value = true
    operation.value = label
    error.value = null
    try {
      return await action()
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 409 || cause.uncertain) && slotId.value !== null) {
        try {
          if (label === '删除存档') {
            saves.value = await api.listSaves()
            if (saves.value.some(slot => slot.slot_id === slotId.value)) await readCurrent(slotId.value)
            else {
              const nextId = saves.value[0]?.slot_id ?? (await api.createSave('初入仙门')).slot_id
              await enterSlot(nextId, true)
              saves.value = await api.listSaves()
            }
          } else await readCurrent(slotId.value)
          void loadWeapons(true)
          error.value = cause.status === 409
            ? '进度已有更新，已为你同步。请确认当前状态后继续。'
            : '已重新确认最新进度，请查看结果后继续。'
        } catch { error.value = '尚未确认最新进度，请恢复连接后刷新。' }
      } else error.value = cause instanceof Error ? cause.message : String(cause)
      return null
    } finally {
      busy.value = false
      operation.value = ''
    }
  }

  function currentSlot(): number {
    if (slotId.value === null) throw new Error('请先选择一个存档。')
    return slotId.value
  }

  async function enterSlot(id: number, collect: boolean) {
    const savedParty = readPreferences().parties?.[String(id)]
    slotId.value = id
    revision.value = 0
    state.value = null
    lastRun.value = null
    lastSettle.value = null
    notice.value = null
    party.value = []
    training.value = null
    trainingFor.value = null
    trainingLoading.value = false
    trainingRequest += 1
    weapons.value = []
    weaponsRequest += 1
    if (collect) {
      const result = await api.settle(id)
      applySnapshot(result, id)
      lastSettle.value = result
    } else applySnapshot(await api.getSave(id), id)
    cleanParty(Array.isArray(savedParty) ? savedParty : [])
    await loadWeapons(true)
    remember()
  }

  async function bootstrap(): Promise<void> {
    await guard('载入宗门', async () => {
      catalog.value = await api.catalog()
      saves.value = await api.listSaves()
      const preferred = readPreferences().slotId
      const selected = saves.value.find(slot => slot.slot_id === preferred) ?? saves.value[0]
      const id = selected?.slot_id ?? (await api.createSave('初入仙门')).slot_id
      await enterSlot(id, true)
      saves.value = await api.listSaves()
      ready.value = true
    })
  }

  async function loadSave(): Promise<void> {
    await guard('同步进度', async () => { await readCurrent(currentSlot()) })
  }

  async function settle(): Promise<SettleResult | null> {
    return guard('收取收益', async () => {
      const id = currentSlot()
      const result = await api.settle(id, revision.value)
      applySnapshot(result, id)
      lastSettle.value = result
      notice.value = `已收取 ${result.elapsed_hours.toFixed(1)} 小时收益：修为 +${result.gained.cultivation.toFixed(1)}，灵石 +${result.gained.spirit_stone.toFixed(1)}`
      return result
    })
  }

  async function startRun(partyIds: string[]): Promise<void> {
    await guard('进入问道塔', async () => {
      const id = currentSlot()
      const result = await api.startRun(id, partyIds, revision.value)
      lastRun.value = null
      applySnapshot(result, id)
    })
  }

  function toggleParty(id: string): void {
    if (busy.value || status.value !== 'idle') return
    if (party.value.includes(id)) party.value = party.value.filter(member => member !== id)
    else {
      const disciple = disciples.value.find(d => d.id === id)
      if (!disciple || disciple.busy) return
      if (state.value?.duty_slots.some(member => member.disciple_id === id)) {
        notice.value = '这位弟子正在值守，请先在演武场卸任。'
        return
      }
      if (party.value.length >= (catalog.value?.rules.max_party ?? 6)) {
        notice.value = '队伍已满，请先移除一名弟子。'
        return
      }
      party.value = [...party.value, id]
    }
    remember()
  }

  function moveParty(id: string, offset: -1 | 1): void {
    if (busy.value || status.value !== 'idle') return
    const from = party.value.indexOf(id)
    const to = from + offset
    if (from < 0 || to < 0 || to >= party.value.length) return
    const ordered = [...party.value]
    const moving = ordered[from]!
    ordered[from] = ordered[to]!
    ordered[to] = moving
    party.value = ordered
    remember()
  }

  async function choose(index: number): Promise<void> {
    await guard('迎战', async () => {
      const id = currentSlot()
      applySnapshot(await api.choose(id, index, revision.value), id)
    })
  }

  async function pickAffix(affixId: string): Promise<void> {
    await guard('领悟词条', async () => {
      const id = currentSlot()
      applySnapshot(await api.pickAffix(id, affixId, revision.value), id)
    })
  }

  async function settleRun(): Promise<RunSettleResult | null> {
    return guard('结算出征', async () => {
      const id = currentSlot()
      const result = await api.settleRun(id, revision.value)
      applySnapshot(result, id)
      lastRun.value = result
      return result
    })
  }

  async function assignDuty(discipleId: string): Promise<void> {
    await guard('安排值守', async () => {
      const id = currentSlot()
      applySnapshot(await api.assignDuty(id, revision.value, discipleId), id)
      remember()
      notice.value = '值守已安排，产出已更新。'
    })
  }

  async function unassignDuty(discipleId: string): Promise<void> {
    await guard('调整值守', async () => {
      const id = currentSlot()
      applySnapshot(await api.unassignDuty(id, revision.value, discipleId), id)
      notice.value = '弟子已卸任，可以编入出征队伍。'
    })
  }

  async function recruit(templateId: string): Promise<void> {
    await guard('招贤纳士', async () => {
      const id = currentSlot()
      if (state.value?.unlocks.includes(templateId)) {
        notice.value = '已拥有该弟子，请在培养界面突破境界。'
        return
      }
      const result = await api.recruit(id, templateId, revision.value)
      applySnapshot(result, id)
      const name = catalog.value?.disciples[templateId]?.name ?? '弟子'
      notice.value = `${name}已加入宗门，可以安排值守或编入队伍。`
      await loadTraining(result.disciple.id)
    })
  }

  async function craft(recipeId: string): Promise<void> {
    await guard('炼制', async () => {
      const id = currentSlot()
      applySnapshot(await api.craft(id, recipeId, revision.value), id)
      const recipe = catalog.value?.recipes[recipeId]
      notice.value = recipe?.kind === 'pill'
        ? `${recipe?.name ?? '丹药'}已炼成 1 颗，存入行囊。`
        : `${recipe?.name ?? '法器'}炼制完成，宗门永久加成已生效。`
    })
  }

  async function usePill(itemId: string, target: string): Promise<void> {
    await guard('服用丹药', async () => {
      const id = currentSlot()
      const result = await api.useItem(id, itemId, target, revision.value)
      applySnapshot(result, id)
      const name = catalog.value?.recipes[result.item_id]?.name ?? '丹药'
      const discipleName = catalog.value?.disciples[result.disciple.template_id]?.name ?? '弟子'
      notice.value = `${discipleName}已服用${name}。`
      await loadTraining(target)
    })
  }

  async function craftWeapon(weaponId: string): Promise<void> {
    await guard('锻造专武', async () => {
      const id = currentSlot()
      const result = await api.craftWeapon(id, weaponId, revision.value)
      applySnapshot(result, id)
      weaponsRequest += 1
      weapons.value = result.weapons
      const name = result.weapons.find(weapon => weapon.id === weaponId)?.name ?? '专武'
      notice.value = `${name}锻造完成，已存入行囊。`
    })
  }

  async function equipWeapon(weaponId: string, discipleId: string): Promise<void> {
    await guard('装备专武', async () => {
      const id = currentSlot()
      const result = await api.equipWeapon(id, weaponId, discipleId, revision.value)
      applySnapshot(result, id)
      weaponsRequest += 1
      weapons.value = result.weapons
      const name = result.weapons.find(weapon => weapon.id === weaponId)?.name ?? '专武'
      notice.value = `${name}已装备。`
      await loadTraining(discipleId)
    })
  }

  async function unequipWeapon(discipleId: string): Promise<void> {
    await guard('卸下专武', async () => {
      const id = currentSlot()
      const result = await api.unequipWeapon(id, discipleId, revision.value)
      applySnapshot(result, id)
      weaponsRequest += 1
      weapons.value = result.weapons
      notice.value = '专武已卸下并放回行囊。'
      await loadTraining(discipleId)
    })
  }

  async function upgrade(discipleId: string): Promise<void> {
    await guard('修炼提升', async () => {
      const id = currentSlot()
      const result = await api.upgrade(id, discipleId, revision.value)
      applySnapshot(result, id)
      notice.value = `修炼完成，等级提升至 ${result.disciple.level}。`
      await loadTraining(discipleId)
    })
  }

  async function breakthrough(discipleId: string): Promise<void> {
    await guard('境界突破', async () => {
      const id = currentSlot()
      const result = await api.breakthrough(id, discipleId, revision.value)
      applySnapshot(result, id)
      notice.value = `突破完成，境界提升至 ${result.disciple.realm}。`
      await loadTraining(discipleId)
    })
  }

  async function loadSaves(): Promise<void> {
    try { saves.value = await api.listSaves() }
    catch (cause) { error.value = cause instanceof Error ? cause.message : String(cause) }
  }

  async function switchSave(id: number): Promise<void> {
    await guard('切换宗门', async () => { await enterSlot(id, true) })
  }

  async function createSave(name: string): Promise<void> {
    await guard('开创新宗门', async () => {
      const result = await api.createSave(name)
      await enterSlot(result.slot_id, false)
      await loadSaves()
    })
  }

  async function duplicateSave(id: number, name: string): Promise<void> {
    await guard('复制存档', async () => {
      await api.duplicateSave(id, name)
      await loadSaves()
      notice.value = '存档副本已建立。'
    })
  }

  async function deleteSave(id: number): Promise<void> {
    await guard('删除存档', async () => {
      await api.deleteSave(id)
      await loadSaves()
      if (slotId.value === id) {
        const nextId = saves.value[0]?.slot_id ?? (await api.createSave('初入仙门')).slot_id
        await enterSlot(nextId, true)
        await loadSaves()
      }
    })
  }

  async function importSave(payload: unknown): Promise<void> {
    await guard('导入存档', async () => {
      const result = await api.importSave(payload)
      await enterSlot(result.slot_id, true)
      await loadSaves()
      notice.value = '存档已导入。'
    })
  }

  return {
    slotId, revision, state, run, catalog, lastRun, lastSettle, saves, party, busy, ready,
    operation, error, notice, noticeId, disciples, resources, status, production, battleResult,
    training, trainingFor, trainingLoading, weapons,
    bootstrap, loadSave, refresh: settle, settle, startRun, toggleParty, moveParty, choose, pickAffix,
    settleRun, assignDuty, unassignDuty, recruit, craft, usePill, craftWeapon, equipWeapon, unequipWeapon,
    loadWeapons, upgrade, breakthrough, loadTraining,
    loadSaves, switchSave,
    createSave, duplicateSave, deleteSave, importSave,
    dismissNotice: () => { notice.value = null },
    clearError: () => { error.value = null },
  }
})
