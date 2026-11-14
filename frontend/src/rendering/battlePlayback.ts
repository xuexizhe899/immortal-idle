import type { BattleResult } from '../api/client'

export type BattleEvent = BattleResult['events'][number]
export type BattleUnit = BattleResult['initial_units'][number]
export type BattleEffect = BattleEvent['effects'][number]
export type PlaybackMode = 'key' | 'all' | 'result'

// 摘要只缩短播放，所有帧仍直接取服务端快照，完整战报始终保留。
export function playbackIndices(events: BattleEvent[], mode: PlaybackMode): number[] {
  if (mode === 'result') return []
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

export function affixSourceText(affixes: BattleEffect['affixes'] = [], names?: ReadonlyMap<string, string>): string {
  const stats: Record<string, string> = { atk: '攻击', def: '防御', hp: '气血', spd: '身法', damage: '伤害', healing: '治疗', shielding: '护盾', taken_damage: '减伤' }
  return affixes.map(source => `${names?.get(source.unit_id) ?? source.unit_id}·${source.name} ${stats[source.stat] ?? source.stat} ${source.value >= 0 ? '+' : ''}${Math.round(source.value * 10000) / 100}%`).join('；')
}

export function effectLabel(effect: BattleEffect, unitNames?: ReadonlyMap<string, string>): string {
  const names: Record<string, string> = { atk: '攻击', def: '防御', spd: '身法' }
  const text = effect.kind === 'damage'
    ? `${effect.amount ? `−${effect.amount}` : '未失血'}${effect.absorbed ? ` · 盾挡 ${effect.absorbed}` : ''}`
    : effect.kind === 'heal' ? `气血 +${effect.amount}`
    : effect.kind === 'shield' ? `护盾 +${effect.amount}`
    : `${names[effect.stat] ?? effect.stat} ${effect.value >= 0 ? '+' : ''}${Math.round(effect.value * 100)}%`
  // 飘字保留实际数值；战报只附上服务端确认参与本次效果的道法修正，旧事件不补猜。
  const sources = unitNames ? affixSourceText(effect.affixes, unitNames) : ''
  return sources ? `${text} · 道法修正：${sources}` : text
}
