import type { GameState } from '../../api/client'

export interface CityActor {
  id: string
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

export const CITY_BUILDINGS = [
  { id: 'main_hall', panel: 'sect', x: 0, z: -7, width: 9, depth: 6 },
  { id: 'library', panel: 'codex', x: -10, z: -6, width: 6, depth: 5 },
  { id: 'dock', panel: 'expedition', x: 12, z: -6, width: 7, depth: 5 },
  { id: 'drill', panel: 'duty', x: -11, z: 3, width: 7, depth: 6 },
  { id: 'tower', panel: 'tower', x: 11, z: 3, width: 4, depth: 4 },
  { id: 'forge', panel: 'forge', x: -5, z: 9, width: 5, depth: 4 },
  { id: 'alchemy', panel: 'alchemy', x: 5, z: 9, width: 5, depth: 4 },
] as const

const IDLE_POSITIONS = [
  [-4, -1], [-1, 0], [3, -1], [6, 1],
  [-5, 3], [-2, 4], [2, 3], [4, 4],
  [-4, 6], [0, 6], [2, 5.5], [7, 6],
  [-6.5, 0], [7, -2], [-2, -2.3], [2, -2.3],
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
      ? [-13.2 + index % 4 * 1.5, 6.4 + Math.floor(index / 4) * 1.2]
      : IDLE_POSITIONS[index]!
    return {
      id: disciple.id,
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
