import type { GameState } from '../../api/client'

export interface CityActor {
  id: string
  templateId: string
  name: string
  image: string
  x: number
  z: number
  injured: boolean
  duty: boolean
}

export interface CameraPose {
  x: number
  z: number
  zoom: number
}

export const CITY_PLAZA = { x: 0, z: 1.8, width: 26, depth: 22 } as const

export const CITY_BUILDINGS = [
  { id: 'main_hall', panel: 'sect', x: 0, z: -18, width: 9, depth: 6 },
  { id: 'library', panel: 'codex', x: -19, z: -15, width: 6, depth: 5 },
  { id: 'dock', panel: 'expedition', x: 20, z: -15, width: 7, depth: 5 },
  { id: 'drill', panel: 'duty', x: -23, z: 4, width: 7, depth: 6 },
  { id: 'tower', panel: 'tower', x: 23, z: 4, width: 4, depth: 4 },
  { id: 'forge', panel: 'forge', x: -14, z: 22, width: 5, depth: 4 },
  { id: 'alchemy', panel: 'alchemy', x: 14, z: 22, width: 5, depth: 4 },
] as const

// 门路停在广场边缘，南侧工坊从外侧绕回，避免穿过屋身和台阶。
export const CITY_BUILDING_PATHS = [
  { id: 'main_hall', points: [[0, -13.6], [0, -9.2]] },
  { id: 'library', points: [[-19, -11.1], [-19, -6], [-13, -6]] },
  { id: 'dock', points: [[20, -11.1], [20, -6], [13, -6]] },
  { id: 'drill', points: [[-23, 8.4], [-18, 8.4], [-13, 8.4]] },
  { id: 'tower', points: [[23, 7.4], [18, 7.4], [13, 7.4]] },
  { id: 'forge', points: [[-14, 25.4], [-18.5, 25.4], [-18.5, 12.8], [-10, 12.8]] },
  { id: 'alchemy', points: [[14, 25.4], [18.5, 25.4], [18.5, 12.8], [10, 12.8]] },
] as const

const IDLE_POSITIONS = [
  [-8, -5], [-3, -5], [3, -5], [8, -5],
  [-8, -1], [-3, -1], [3, -1], [8, -1],
  [-8, 3], [-3, 3], [3, 3], [8, 3],
  [-8, 7], [-3, 7], [3, 7], [8, 7],
] as const

/** 只投影当前存档中的常驻弟子；出征和驻守者不会同时出现在宗门。 */
export function projectCityActors(
  state: Pick<GameState, 'disciples' | 'duty_slots' | 'sects' | 'active_run'> | null | undefined,
  describe: (templateId: string) => { name: string; image: string },
): CityActor[] {
  if (!state) return []
  const absent = new Set(state.active_run?.party ?? [])
  for (const unit of state.active_run?.party_snapshot?.combatants ?? []) absent.add(unit.id)
  for (const sect of state.sects) {
    for (const slot of sect.garrison) absent.add(slot.disciple_id)
  }
  const duties = new Set(state.duty_slots.map(slot => slot.disciple_id))
  const residents = state.disciples.filter(disciple => !disciple.busy && !absent.has(disciple.id))
  // 场景人数有显示上限，先保留实际值守者，顺序与当前存档一致。
  const visible = [
    ...residents.filter(disciple => duties.has(disciple.id)),
    ...residents.filter(disciple => !duties.has(disciple.id)),
  ].slice(0, 16)
  let dutyIndex = 0
  let idleIndex = 0
  return visible.map(disciple => {
    const duty = duties.has(disciple.id)
    const index = duty ? dutyIndex++ : idleIndex++
    const [x, z] = duty
      ? [-26.5 + index % 4 * 2, 9.5 + Math.floor(index / 4) * 1.8]
      : IDLE_POSITIONS[index]!
    return {
      id: disciple.id,
      templateId: disciple.template_id,
      ...describe(disciple.template_id),
      x, z, duty,
      injured: disciple.injury_stacks > 0,
    }
  })
}

/** 相机偏移与缩放仅影响画面，不写回存档。 */
export function clampCityCamera(pose: CameraPose, minimumZoom = .75): CameraPose {
  return {
    x: Math.max(-16, Math.min(16, pose.x)),
    z: Math.max(-12, Math.min(12, pose.z)),
    zoom: Math.max(minimumZoom, Math.min(2, pose.zoom)),
  }
}
