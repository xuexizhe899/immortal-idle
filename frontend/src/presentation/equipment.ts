import type { GearView } from '../api/client'
import { number } from '../shared/format'
import { statNames } from './gameText'

export const equipmentSlots = ['weapon', 'armor', 'boots', 'ring'] as const
export const equipmentSlotNames: Record<string, string> = { weapon: '武器', armor: '盔甲', boots: '靴子', ring: '戒指' }
const statOrder = ['hp', 'atk', 'def', 'spd', 'damage', 'healing', 'shielding']

export function equipmentStatName(stat: string): string {
  return stat === 'spd' ? '身法' : statNames[stat] ?? stat
}

export function equipmentPercent(value: number, signed = true): string {
  return `${signed && value > 0 ? '+' : ''}${number(value * 100, 2)}%`
}

export function equipmentStats(stats: Record<string, number>) {
  return Object.entries(stats).map(([stat, value]) => ({ stat, name: equipmentStatName(stat), value, text: equipmentPercent(value) }))
}

// 只比较服务端给出的装备增益，不预测最终角色属性、战力或战斗结果。
export function equipmentComparison(current: Record<string, number>, candidate: Record<string, number>) {
  return [...new Set([...Object.keys(current), ...Object.keys(candidate)])]
    .sort((a, b) => (statOrder.indexOf(a) < 0 ? 99 : statOrder.indexOf(a)) - (statOrder.indexOf(b) < 0 ? 99 : statOrder.indexOf(b)))
    .map(stat => ({
      stat, name: equipmentStatName(stat), current: current[stat] ?? 0, candidate: candidate[stat] ?? 0,
      delta: Math.round(((candidate[stat] ?? 0) - (current[stat] ?? 0)) * 1_000_000) / 1_000_000,
    }))
}

export function equipmentAffixText(stat: string, value: number, grade: number): string {
  return stat ? `${equipmentStatName(stat)} ${equipmentPercent(value)} · ${grade} 档` : '无副属性'
}

export function smeltBlockReason(item: GearView, readOnly = false): string {
  if (readOnly) return '出征结束后可熔炼装备'
  // 确认按钮独立保护归属、锁定与未决洗练，避免旧列表漏显原因时误点。
  if (item.equipped_by) return '请先卸下装备'
  if (item.locked) return '请先解除锁定'
  if (item.pending_affix) return '请先选择洗练结果'
  return item.smelt_reason
}
