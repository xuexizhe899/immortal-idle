import type { Catalog, GameState, WorldMap } from '../api/client'

export interface MaterialSource {
  kind: 'idle' | 'duty' | 'garrison' | 'tower' | 'conquest' | 'retrial' | 'dungeon' | 'invasion' | 'smelt'
  label: string
  detail: string
  rate?: number
  panel: 'duty' | 'expedition' | 'tower' | 'forge'
  available: boolean
  sectId?: string
  regionId?: number
  blockedReason?: string
}

const KIND_NAMES: Record<string, string> = { battle: '普通', elite: '精英', boss: '首领' }

/** 材料来源保留准确宗门与地区；战斗奖励只展示服务端地图预览。 */
export function materialSources(catalog: Catalog | null, state: GameState | null, worldMap: WorldMap | null = null): Record<string, MaterialSource[]> {
  const matrix: Record<string, MaterialSource[]> = {}
  if (!catalog) return matrix
  const training = 1 + .25 * ((state?.facility_levels.training ?? 1) - 1)
  const currentRegion = state?.world?.current_region ?? 1
  const sects = (state?.sects ?? []).map(sect => {
    const regionId = sect.region_id ?? 1
    const region = worldMap?.regions.find(item => item.id === regionId)
    const node = region?.nodes.find(item => item.kind === 'sect' && item.sect_id === sect.id)
    const opened = region?.unlocked ?? (state?.world?.unlocked_regions ?? [1]).includes(regionId)
    const areaOpened = (sect.area ?? 1) <= (state?.world?.unlocked_areas[String(regionId)] ?? 1)
    const reason = !opened ? '需先飞升开放该地区' : !areaOpened ? '需先击败前一片区守关首领' : node?.locked ? node.reason : ''
    const place = region?.name ?? `第${regionId}地区`
    const location = `${place}${regionId !== currentRegion && !reason ? ' · 需先切换图层' : ''}`
    const blocked = !opened ? '地区未开放' : reason ? '片区未开放' : ''
    return { sect, node, regionId, location, reason, blocked }
  })
  for (const id of Object.keys(catalog.materials)) {
    const sources: MaterialSource[] = []
    if (id === 'lian_qi_jing_cui') {
      sources.push({ kind: 'dungeon', label: '探索秘境', detail: '沿途取得材料，失败仍带回此前所得', panel: 'expedition', available: true })
      sources.push({ kind: 'smelt', label: '熔炼多余装备', detail: '在炼器阁查看具体回收数量', panel: 'forge', available: true })
    }
    if (id === 'sheng_xian_ling') sources.push({ kind: 'invasion', label: '地区最终关键入侵', detail: '击退最后片区的关键入侵，首胜获得升仙令', panel: 'expedition', available: true })
    const base = catalog.production.materials[id] ?? 0
    if (base > 0) {
      sources.push({ kind: 'idle', label: '挂机基础', detail: '宗门基础产出，离线同样结算', rate: base, panel: 'duty', available: true })
      const specialists = Object.values(catalog.disciples).filter(item => item.production_specialty === id)
      if (specialists.length) sources.push({ kind: 'duty', label: '值守专长', detail: specialists.map(item => item.name).join('、'), rate: base * training, panel: 'duty', available: true })
    }
    for (const { sect, regionId, location, reason, blocked } of sects) {
      if (sect.material_id !== id && sect.special_material_id !== id) continue
      const special = sect.special_material_id === id
      sources.push({
        kind: 'garrison', label: `驻守 · ${sect.name}`,
        detail: `${location} · ${reason || (sect.conquered ? '已攻克' : '需先攻克')} · ${special ? '特殊材料' : '普通材料'}，实际产出见驻守`,
        panel: 'expedition', available: !reason && sect.conquered,
        sectId: sect.id, regionId, blockedReason: blocked || (sect.conquered ? '' : '需攻克'),
      })
    }
    const towerRewards = worldMap?.regions.find(region => region.id === currentRegion)?.tower_rewards
    const towerKinds = Object.entries(towerRewards ?? catalog.mode.rewards ?? {}).filter(([, reward]) => id in reward)
    if (towerKinds.length) sources.push({
      kind: 'tower', label: '问道塔',
      detail: towerRewards ? towerKinds.map(([kind, reward]) => `${KIND_NAMES[kind] ?? kind} +${reward[id]}`).join(' · ') : '载入当前地区地图后查看奖励',
      panel: 'tower', available: true,
    })
    for (const { sect, regionId, location, reason, blocked } of sects) {
      if (!(id in sect.loot)) continue
      sources.push({
        kind: 'conquest', label: `首胜 · ${sect.name}`,
        detail: `${location} · ${reason || (sect.conquered ? '首胜已领取' : `攻克首胜 +${sect.loot[id]}`)}`,
        panel: 'expedition', available: !reason && !sect.conquered,
        sectId: sect.id, regionId, blockedReason: blocked || (sect.conquered ? '已领取' : ''),
      })
    }
    for (const { sect, node, regionId, location, reason, blocked } of sects) {
      const rewards = node?.retrial_rewards
      const knownRewards = rewards ?? catalog.sect_styles?.find(style => style.name === sect.style)?.retrial_reward ?? {}
      if (!(id in knownRewards)) continue
      sources.push({
        kind: 'retrial', label: `论道 · ${sect.name}`,
        detail: `${location} · ${reason || (!sect.conquered ? '需先攻克此宗门' : rewards ? `胜利 +${rewards[id]}` : '载入地图后查看奖励')}`,
        panel: 'expedition', available: !reason && sect.conquered,
        sectId: sect.id, regionId, blockedReason: blocked || (sect.conquered ? '' : '需攻克'),
      })
    }
    matrix[id] = sources
  }
  return matrix
}
