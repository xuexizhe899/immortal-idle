import type { ActiveRun, Catalog, DiscipleState } from '../api/client'
import { number } from '../shared/format'

export type DisplayEffect = NonNullable<Catalog['affixes'][string]['effects']>[number]
export type DisplaySkill = Catalog['skills'][string]
export type DisplayCatalog = Catalog
export const leanNames: Record<string, string> = { attack: '攻', defense: '防', support: '辅', craft: '炼' }
export const leanDescriptions: Record<string, string> = { attack: '值守提升修为产出', defense: '值守提升灵石产出', support: '值守提升行动力恢复与伤势消退', craft: '值守提升材料产出' }
export const statNames: Record<string, string> = { hp: '气血', atk: '攻击', def: '防御', spd: '速度', damage: '伤害', healing: '治疗', shielding: '护盾', cultivation: '修为', spirit_stone: '灵石', stamina: '行动力', reputation: '声望', cultivation_rate: '修为产出', spirit_stone_rate: '灵石产出', stamina_rate: '行动力恢复', material_rate: '材料产出', injury_rate: '伤势消退' }
export const rarityNames: Record<number, string> = { 1: '良才', 2: '英杰', 3: '天骄' }
export function description(value: string | undefined): string { return (value ?? '').replace(/\b[a-z_]+\b/g, token => statNames[token] ?? token) }
export function effectText(effect: Pick<DisplayEffect, 'stat' | 'mode' | 'value'>): string { const value = effect.mode === 'add_pct' ? `${number(effect.value * 100, 1)}%` : number(effect.value, 1); return `${statNames[effect.stat] ?? effect.stat} ${effect.value >= 0 ? '+' : ''}${value}` }
export function snapshotAffixes(pool: NonNullable<ActiveRun['party_snapshot']>['affix_pool'] = []) {
  const groupNames: Record<string, string> = { fengrui: '锋锐', jianshou: '坚守', qimou: '奇谋' }
  return Object.fromEntries(pool.map(affix => {
    const id = String(affix.id)
    const group = typeof affix.group === 'string' ? affix.group : ''
    // 旧出征只保存 effects；沿用本局效果生成说明，不能借用新版同名道法的规则。
    const text = typeof affix.description === 'string' && affix.description
      ? affix.description
      : ((affix.effects ?? []) as DisplayEffect[]).map(effectText).join('，')
    return [id, {
      name: typeof affix.name === 'string' ? affix.name : id,
      group,
      groupName: typeof affix.group_name === 'string' ? affix.group_name : groupNames[group] ?? group,
      description: text || '本局未记录道法说明',
    }] as const
  }))
}
export function injuryText(disciple: DiscipleState): string { if (!disciple.injury_stacks) return '状态良好'; if (!disciple.injured_until) return `${disciple.injury_stacks} 层伤势`; const at = new Date(disciple.injured_until); return `${disciple.injury_stacks} 层伤势 · ${at.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })} 消退` }
export function resourceName(id: string, catalog?: DisplayCatalog | null): string { return statNames[id] ?? catalog?.materials[id] ?? catalog?.recipes[id]?.name ?? catalog?.weapons[id]?.name ?? id }
