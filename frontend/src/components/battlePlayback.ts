import type { BattleResult } from '../api/client'

export type BattleEvent = BattleResult['events'][number]
export type BattleUnit = BattleResult['initial_units'][number]
export type BattleEffect = BattleEvent['effects'][number]

// 摘要只缩短播放，所有帧仍直接取服务端快照，完整战报始终保留。
export function playbackIndices(events: BattleEvent[], mode: 'key' | 'all'): number[] {
  if (mode === 'all' || events.length <= 10) return events.map((_, index) => index)
  const indexed = events.map((event, index) => ({ event, index }))
  const bonds = indexed.filter(({ event }) => event.bonds.length).map(({ index }) => index)
  const skills = indexed.filter(({ event }) => event.skill_id !== 'basic_attack')
    .map(({ index }) => index)
  const chosen = [0, ...bonds.slice(0, 3), ...skills.slice(0, 2)]
  for (let step = 1; step <= 3; step++) chosen.push(Math.floor((events.length - 1) * step / 4))
  chosen.push(events.length - 1)
  return [...new Set(chosen)].sort((a, b) => a - b)
}

export function battleUnitsAt(result: BattleResult, index: number): BattleUnit[] {
  if (index < 0) return result.initial_units
  if (index >= result.events.length) return result.final_units
  return result.events[index]!.units
}

export function effectLabel(effect: BattleEffect): string {
  if (effect.kind === 'damage') return `${effect.amount ? `−${effect.amount}` : '未失血'}${effect.absorbed ? ` · 盾挡 ${effect.absorbed}` : ''}`
  if (effect.kind === 'heal') return `气血 +${effect.amount}`
  if (effect.kind === 'shield') return `护盾 +${effect.amount}`
  const names: Record<string, string> = { atk: '攻击', def: '防御', spd: '身法' }
  return `${names[effect.stat] ?? effect.stat} ${effect.value >= 0 ? '+' : ''}${Math.round(effect.value * 100)}%`
}
