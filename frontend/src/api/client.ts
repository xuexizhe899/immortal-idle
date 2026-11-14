import type { components } from '../generated/api'

type Schemas = components['schemas']

export type GameState = Schemas['GameState-Output']
export type SaveSlotMeta = Schemas['SaveSlotMeta']
export type DiscipleState = Schemas['DiscipleState-Output']
export type ActiveRun = Schemas['ActiveRun-Output']
export type RunNode = Schemas['RunNode-Output']
export type Catalog = Schemas['CatalogResponse']
export type CityLayout = Schemas['CityLayout']
export type CityHotspot = Schemas['CityHotspot']
export type SaveContent = Schemas['GameSnapshot']
export type RunPayload = Schemas['RunResponse']
export type SettleResult = Schemas['SettleResponse']
export type RunSettleResult = Schemas['RunSettleResponse']
export type DutyChange = Schemas['DutyResponse']
export type DutyPayload = DutyChange
export type RecruitResult = Schemas['RecruitResponse']
export type CraftResult = Schemas['CraftResponse']
export type UseItemResult = Schemas['UseItemResponse']
export type WeaponView = Schemas['WeaponView']
export type WeaponList = Schemas['WeaponListResponse']
export type WeaponResult = Schemas['WeaponCommandResponse']
export type UpgradeResult = Schemas['UpgradeResponse']
export type TrainingStats = Schemas['TrainingStats']
export type TrainingStep = Schemas['TrainingStep']
export type TrainingPreview = Schemas['TrainingPreview']
export type BreakthroughResult = Schemas['BreakthroughResponse']
export type Production = Schemas['ProductionCatalog']
export type BattleResult = Schemas['BattleSummary-Output']
export type FacilityView = Schemas['FacilityView']
export type FacilityList = Schemas['FacilityListResponse']
export type FacilityResult = Schemas['FacilityCommandResponse']
export type RecipeView = Schemas['RecipeView']
export type RecipeList = Schemas['CraftListResponse']
export type HealPreview = Schemas['HealPartyPreview']
export type HealResult = Schemas['HealPartyResponse']

export class ApiError extends Error {
  readonly status: number
  readonly uncertain: boolean

  constructor(message: string, status: number, uncertain = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.uncertain = uncertain
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 20_000)
  try {
    const response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      signal: controller.signal,
    })
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null)
      const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
      const message = typeof detail === 'string'
        ? detail
        : response.status === 422 ? '操作信息已失效，请刷新后重试。' : `请求失败（${response.status}），请稍后重试。`
      throw new ApiError(message, response.status)
    }
    return await response.json() as T
  } catch (cause) {
    if (cause instanceof ApiError) throw cause
    throw new ApiError(controller.signal.aborted
      ? '连接超时，正在确认最新进度。'
      : '暂时无法连接宗门，请检查网络后重试。', 0, init?.method === 'POST' || init?.method === 'DELETE')
  } finally {
    window.clearTimeout(timeout)
  }
}

function post<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: payload === undefined ? undefined : JSON.stringify(payload) })
}

export const api = {
  catalog: () => request<Catalog>('/catalog'),
  listSaves: () => request<SaveSlotMeta[]>('/saves'),
  createSave: (name: string) => post<{ slot_id: number }>('/saves', { name }),
  getSave: (slotId: number) => request<SaveContent>(`/saves/${slotId}`),
  settle: (slotId: number, revision?: number) => post<SettleResult>(`/saves/${slotId}/settle`, revision ? { revision } : undefined),
  getRun: (slotId: number) => request<RunPayload>(`/saves/${slotId}/run`),
  startRun: (slotId: number, party: string[], revision: number, mode: 'tower' | 'expedition' = 'tower', options: { sect_id?: string; tower_tier?: number } = {}) => post<RunPayload>(`/saves/${slotId}/run/start`, { party, revision, ...(mode === 'tower' ? {} : { mode }), ...options }),
  arena: (slotId: number, party: string[], revision: number) => post<RunPayload>(`/saves/${slotId}/run/arena`, { party, revision }),
  retreat: (slotId: number, revision: number) => post<RunPayload>(`/saves/${slotId}/run/retreat`, { revision }),
  choose: (slotId: number, choice: number, revision: number) => post<RunPayload>(`/saves/${slotId}/run/choose`, { choice, revision }),
  pickAffix: (slotId: number, affixId: string, revision: number) => post<RunPayload>(`/saves/${slotId}/run/affix`, { affix_id: affixId, revision }),
  settleRun: (slotId: number, revision: number) => post<RunSettleResult>(`/saves/${slotId}/run/settle`, { revision }),
  assignDuty: (slotId: number, revision: number, discipleId: string) => post<DutyChange>(`/saves/${slotId}/duty/assign`, { revision, disciple_id: discipleId }),
  unassignDuty: (slotId: number, revision: number, discipleId: string) => post<DutyChange>(`/saves/${slotId}/duty/unassign`, { revision, disciple_id: discipleId }),
  recruit: (slotId: number, templateId: string, revision: number) => post<RecruitResult>(`/saves/${slotId}/recruit`, { template_id: templateId, revision }),
  recipes: (slotId: number, grade: number) => request<RecipeList>(`/saves/${slotId}/craft?grade=${grade}`),
  craft: (slotId: number, recipeId: string, revision: number, quantity = 1, grade = 1) => post<CraftResult>(`/saves/${slotId}/craft`, { recipe_id: recipeId, revision, quantity, grade }),
  facilities: (slotId: number) => request<FacilityList>(`/saves/${slotId}/facilities`),
  upgradeFacility: (slotId: number, facilityId: string, revision: number) => post<FacilityResult>(`/saves/${slotId}/facilities/upgrade`, { facility_id: facilityId, revision }),
  healPreview: (slotId: number, party: string[]) => post<HealPreview>(`/saves/${slotId}/items/heal-party/preview`, { party }),
  healParty: (slotId: number, party: string[], revision: number) => post<HealResult>(`/saves/${slotId}/items/heal-party`, { party, revision }),
  assignGarrison: (slotId: number, sectId: string, discipleId: string, revision: number) => post<SaveContent>(`/saves/${slotId}/garrison/assign`, { sect_id: sectId, disciple_id: discipleId, revision }),
  unassignGarrison: (slotId: number, sectId: string, discipleId: string, revision: number) => post<SaveContent>(`/saves/${slotId}/garrison/unassign`, { sect_id: sectId, disciple_id: discipleId, revision }),
  useItem: (slotId: number, itemId: string, target: string, revision: number) => post<UseItemResult>(`/saves/${slotId}/items/use`, { item_id: itemId, target, revision }),
  weapons: (slotId: number) => request<WeaponList>(`/saves/${slotId}/weapons`),
  craftWeapon: (slotId: number, weaponId: string, revision: number) => post<WeaponResult>(`/saves/${slotId}/weapons/craft`, { weapon_id: weaponId, revision }),
  upgradeWeapon: (slotId: number, weaponId: string, revision: number) => post<WeaponResult>(`/saves/${slotId}/weapons/upgrade`, { weapon_id: weaponId, revision }),
  equipWeapon: (slotId: number, weaponId: string, discipleId: string, revision: number) => post<WeaponResult>(`/saves/${slotId}/weapons/equip`, { weapon_id: weaponId, disciple_id: discipleId, revision }),
  unequipWeapon: (slotId: number, discipleId: string, revision: number) => post<WeaponResult>(`/saves/${slotId}/weapons/unequip`, { disciple_id: discipleId, revision }),
  upgrade: (slotId: number, discipleId: string, revision: number) => post<UpgradeResult>(`/saves/${slotId}/disciples/${encodeURIComponent(discipleId)}/upgrade`, { revision }),
  training: (slotId: number, discipleId: string) => request<TrainingPreview>(`/saves/${slotId}/disciples/${encodeURIComponent(discipleId)}/training`),
  breakthrough: (slotId: number, discipleId: string, revision: number) => post<BreakthroughResult>(`/saves/${slotId}/disciples/${encodeURIComponent(discipleId)}/breakthrough`, { revision }),
  duplicateSave: (slotId: number, name: string) => post<{ slot_id: number }>(`/saves/${slotId}/duplicate`, { name }),
  deleteSave: (slotId: number) => request<{ ok: boolean }>(`/saves/${slotId}`, { method: 'DELETE' }),
  exportSave: (slotId: number) => request<Schemas['SaveExport']>(`/saves/${slotId}/export`),
  importSave: (payload: unknown) => post<{ slot_id: number }>('/saves/import', payload),
}
