import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  api,
  type Catalog,
  type GameState,
  type RunPayload,
  type RunSettleResult,
  type SaveSlotMeta,
  type SettleResult,
} from '../api/client'

export const useGameStore = defineStore('game', () => {
  const slotId = ref<number | null>(null)
  const revision = ref(0)
  const state = ref<GameState | null>(null)
  const run = ref<RunPayload | null>(null)
  const catalog = ref<Catalog | null>(null)
  const lastRun = ref<RunSettleResult | null>(null)
  const saves = ref<SaveSlotMeta[]>([])
  const party = ref<string[]>([])
  const busy = ref(false)
  const error = ref<string | null>(null)

  const disciples = computed(() => state.value?.disciples ?? [])
  const resources = computed(() => state.value?.resources)
  const status = computed(() => run.value?.status ?? 'idle')

  async function guard<T>(action: () => Promise<T>): Promise<T | null> {
    busy.value = true
    error.value = null
    try {
      return await action()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
      return null
    } finally {
      busy.value = false
    }
  }

  async function loadSave(): Promise<void> {
    if (slotId.value === null) return
    const content = await api.getSave(slotId.value)
    revision.value = content.revision
    state.value = content.state
    run.value = await api.getRun(slotId.value)
  }

  async function bootstrap(): Promise<void> {
    await guard(async () => {
      catalog.value = await api.catalog()
      const saves = await api.listSaves()
      const slot = saves[0] ?? { slot_id: (await api.createSave('初入江湖')).slot_id }
      slotId.value = slot.slot_id
      await loadSave()
    })
  }

  async function settle(): Promise<SettleResult | null> {
    return guard(async () => {
      const result = await api.settle(slotId.value as number)
      revision.value = result.revision
      state.value = result.state
      return result
    })
  }

  async function startRun(partyIds: string[]): Promise<void> {
    await guard(async () => {
      run.value = await api.startRun(slotId.value as number, partyIds)
      await loadSave()
    })
  }

  function toggleParty(id: string): void {
    const index = party.value.indexOf(id)
    if (index >= 0) {
      party.value.splice(index, 1)
    } else if (party.value.length < 5) {
      party.value.push(id)
    }
  }

  async function choose(index: number): Promise<void> {
    await guard(async () => {
      run.value = await api.choose(slotId.value as number, index)
      await loadSave()
    })
  }

  async function pickAffix(affixId: string): Promise<void> {
    await guard(async () => {
      run.value = await api.pickAffix(slotId.value as number, affixId)
      await loadSave()
    })
  }

  async function settleRun(): Promise<RunSettleResult | null> {
    return guard(async () => {
      const result = await api.settleRun(slotId.value as number)
      revision.value = result.revision
      state.value = result.state
      lastRun.value = result
      run.value = await api.getRun(slotId.value as number)
      return result
    })
  }

  async function assignDuty(discipleId: string): Promise<void> {
    await guard(async () => {
      await api.assignDuty(slotId.value as number, revision.value, discipleId)
      await loadSave()
    })
  }

  async function unassignDuty(discipleId: string): Promise<void> {
    await guard(async () => {
      await api.unassignDuty(slotId.value as number, revision.value, discipleId)
      await loadSave()
    })
  }

  async function recruit(templateId: string): Promise<void> {
    await guard(async () => {
      await api.recruit(slotId.value as number, templateId)
      await loadSave()
    })
  }

  async function craft(recipeId: string, target: string | null): Promise<void> {
    await guard(async () => {
      await api.craft(slotId.value as number, recipeId, target)
      await loadSave()
    })
  }

  async function loadSaves(): Promise<void> {
    saves.value = await api.listSaves()
  }

  async function switchSave(id: number): Promise<void> {
    await guard(async () => {
      slotId.value = id
      lastRun.value = null
      await loadSave()
      const result = await api.settle(id)
      revision.value = result.revision
      state.value = result.state
    })
  }

  async function createSave(name: string): Promise<void> {
    await guard(async () => {
      const result = await api.createSave(name)
      await loadSaves()
      slotId.value = result.slot_id
      await loadSave()
    })
  }

  async function duplicateSave(id: number, name: string): Promise<void> {
    await guard(async () => {
      await api.duplicateSave(id, name)
      await loadSaves()
    })
  }

  async function deleteSave(id: number): Promise<void> {
    await guard(async () => {
      await api.deleteSave(id)
      await loadSaves()
      if (slotId.value === id) {
        slotId.value = saves.value[0]?.slot_id ?? null
        if (slotId.value !== null) await loadSave()
      }
    })
  }

  async function importSave(payload: unknown): Promise<void> {
    await guard(async () => {
      const result = await api.importSave(payload)
      await loadSaves()
      slotId.value = result.slot_id
      await loadSave()
    })
  }

  return {
    slotId,
    revision,
    state,
    run,
    catalog,
    lastRun,
    saves,
    party,
    busy,
    error,
    disciples,
    resources,
    status,
    bootstrap,
    loadSave,
    settle,
    startRun,
    toggleParty,
    choose,
    pickAffix,
    settleRun,
    assignDuty,
    unassignDuty,
    recruit,
    craft,
    loadSaves,
    switchSave,
    createSave,
    duplicateSave,
    deleteSave,
    importSave,
  }
})
