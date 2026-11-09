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

export interface CityHotspot {
  id: string
  name: string
  panel: string
  x: number
  y: number
  w: number
  h: number
}

export interface CityLayout {
  background: string
  aspect: number
  hotspots: CityHotspot[]
}

export interface Catalog {
  disciples: Record<
    string,
    { name: string; title: string; lean: string; rarity: number; unlock_cost: { reputation: number } }
  >
  affixes: Record<string, { name: string; group: string }>
  recipes: Record<
    string,
    { name: string; kind: string; inputs: Record<string, number>; special?: string | null }
  >
  materials: Record<string, string>
  city: CityLayout
}

export type DiscipleState = Schemas['DiscipleState']

export interface DutyChange {
  revision: number
  duty: { disciple_id: string; assigned_at: string }[]
  rates: Record<string, number>
}

export interface RecruitResult {
  revision: number
  reputation: number
  disciple: DiscipleState
}

export interface CraftResult {
  revision: number
  bonuses: Record<string, number>
  inventory: Record<string, number>
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

  assignDuty: (slotId: number, revision: number, discipleId: string) =>
    request<DutyChange>(`/saves/${slotId}/duty/assign`, {
      method: 'POST',
      body: JSON.stringify({ revision, disciple_id: discipleId }),
    }),

  unassignDuty: (slotId: number, revision: number, discipleId: string) =>
    request<DutyChange>(`/saves/${slotId}/duty/unassign`, {
      method: 'POST',
      body: JSON.stringify({ revision, disciple_id: discipleId }),
    }),

  recruit: (slotId: number, templateId: string) =>
    request<RecruitResult>(`/saves/${slotId}/recruit`, {
      method: 'POST',
      body: JSON.stringify({ template_id: templateId }),
    }),

  craft: (slotId: number, recipeId: string, target: string | null) =>
    request<CraftResult>(`/saves/${slotId}/craft`, {
      method: 'POST',
      body: JSON.stringify({ recipe_id: recipeId, target }),
    }),

  duplicateSave: (slotId: number, name: string) =>
    request<{ slot_id: number }>(`/saves/${slotId}/duplicate`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  deleteSave: (slotId: number) =>
    request<{ ok: boolean }>(`/saves/${slotId}`, { method: 'DELETE' }),

  exportSave: (slotId: number) =>
    request<{ name: string; schema_version: number; state: GameState }>(
      `/saves/${slotId}/export`,
    ),

  importSave: (payload: unknown) =>
    request<{ slot_id: number }>('/saves/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
