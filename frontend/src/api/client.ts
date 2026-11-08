import type { components } from '../generated/api'

type Schemas = components['schemas']

export type GameState = Schemas['GameState']
export type SaveSlotMeta = Schemas['SaveSlotMeta']
export type ActiveRun = Schemas['ActiveRun']
export type RunNode = Schemas['RunNode']

export interface SaveContent {
  revision: number
  state: GameState
}

export interface RunPayload {
  revision: number
  status: string
  run: ActiveRun | null
}

export interface SettleResult {
  revision: number
  elapsed_hours: number
  dropped_hours: number
  gained: { cultivation: number; spirit_stone: number; stamina: number }
  warnings: string[]
  state: GameState
}

export interface RunSettleResult {
  revision: number
  cleared: number
  victory: boolean
  loot: Record<string, number>
  state: GameState
}

export interface DutyPayload {
  revision: number
  duty: { disciple_id: string; assigned_at: string }[]
  rates: Record<string, number>
}

export interface Catalog {
  disciples: Record<string, { name: string; title: string; lean: string; rarity: number }>
  affixes: Record<string, { name: string; group: string }>
  recipes: Record<string, { name: string; kind: string }>
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `请求失败（HTTP ${response.status}）`)
  }

  return (await response.json()) as T
}

export const api = {
  catalog: () => request<Catalog>('/catalog'),

  listSaves: () => request<SaveSlotMeta[]>('/saves'),

  createSave: (name: string) =>
    request<{ slot_id: number }>('/saves', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  getSave: (slotId: number) => request<SaveContent>(`/saves/${slotId}`),

  settle: (slotId: number) =>
    request<SettleResult>(`/saves/${slotId}/settle`, { method: 'POST' }),

  getRun: (slotId: number) => request<RunPayload>(`/saves/${slotId}/run`),

  startRun: (slotId: number, party: string[]) =>
    request<RunPayload>(`/saves/${slotId}/run/start`, {
      method: 'POST',
      body: JSON.stringify({ party }),
    }),

  choose: (slotId: number, choice: number) =>
    request<RunPayload>(`/saves/${slotId}/run/choose`, {
      method: 'POST',
      body: JSON.stringify({ choice }),
    }),

  pickAffix: (slotId: number, affixId: string) =>
    request<RunPayload>(`/saves/${slotId}/run/affix`, {
      method: 'POST',
      body: JSON.stringify({ affix_id: affixId }),
    }),

  settleRun: (slotId: number) =>
    request<RunSettleResult>(`/saves/${slotId}/run/settle`, { method: 'POST' }),
}
