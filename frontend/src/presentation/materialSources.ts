import type { Catalog, GameState } from '../api/client'

export interface MaterialSource {
  kind: 'idle' | 'duty' | 'garrison' | 'tower' | 'conquest' | 'retrial'
  label: string
  detail: string
  rate?: number
  panel: 'duty' | 'expedition' | 'tower'
  available: boolean
}

const KIND_NAMES: Record<string, string> = { battle: '普通', elite: '精英', boss: '首领' }

/** 材料来源矩阵：纯展示，速率与一次性奖励分开，全部读 catalog 与当前存档。 */
export function materialSources(catalog: Catalog | null, state: GameState | null): Record<string, MaterialSource[]> {
  const matrix: Record<string, MaterialSource[]> = {}
  if (!catalog) return matrix
  const training = 1 + .25 * ((state?.facility_levels.training ?? 1) - 1)
  const sects = state?.sects ?? []
  for (const id of Object.keys(catalog.materials)) {
    const sources: MaterialSource[] = []
    const base = catalog.production.materials[id] ?? 0
    if (base > 0) {
      sources.push({ kind: 'idle', label: '挂机基础', detail: '宗门基础产出，离线同样结算', rate: base, panel: 'duty', available: true })
      const specialists = Object.values(catalog.disciples).filter(item => item.production_specialty === id)
      if (specialists.length) sources.push({ kind: 'duty', label: '值守专长', detail: specialists.map(item => item.name).join('、'), rate: base * training, panel: 'duty', available: true })
    }
    for (const sect of sects) {
      if (sect.material_id !== id && sect.special_material_id !== id) continue
      const special = sect.special_material_id === id
      sources.push({
        kind: 'garrison', label: `驻守 · ${sect.name}`,
        detail: `${sect.conquered ? '已攻克' : '需先攻克'} · 专长匹配翻倍`,
        rate: (special ? .15 : .5) * sect.level, panel: 'expedition', available: sect.conquered,
      })
    }
    const towerKinds = Object.entries(catalog.mode.rewards ?? {}).filter(([, reward]) => id in reward)
    if (towerKinds.length) sources.push({
      kind: 'tower', label: '问道塔',
      detail: towerKinds.map(([kind, reward]) => `${KIND_NAMES[kind] ?? kind} +${reward[id]}`).join(' · '),
      panel: 'tower', available: true,
    })
    for (const sect of sects) {
      if (!(id in sect.loot)) continue
      sources.push({
        kind: 'conquest', label: `首胜 · ${sect.name}`,
        detail: sect.conquered ? '已攻克领取' : '攻克后一次性',
        panel: 'expedition', available: !sect.conquered,
      })
    }
    for (const style of catalog.sect_styles ?? []) {
      if (!(id in style.retrial_reward)) continue
      const open = sects.some(sect => sect.style === style.name && sect.conquered)
      sources.push({
        kind: 'retrial', label: `论道 · ${style.name}`,
        detail: open ? `胜利 +${style.retrial_reward[id]}` : '需先攻克该流派宗门',
        panel: 'expedition', available: open,
      })
    }
    matrix[id] = sources
  }
  return matrix
}