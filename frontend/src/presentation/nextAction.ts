import type { FacilityView, RecipeView } from '../api/client'

export interface NextAction { label: string; panel: string }

/** 收取后的下一步：可升级 > 缺料 > 可炼；纯展示，点击仍走原入口与原命令。 */
export function pickNextAction(
  facilities: FacilityView[], recipes: RecipeView[],
  held: (id: string) => number, nameOf: (id: string) => string,
): NextAction | null {
  const ready = facilities.find(item => item.upgradeable)
  if (ready) return { label: `可升级${ready.name}`, panel: 'sect' }
  for (const facility of facilities) {
    if (facility.level >= facility.max_level) continue
    const missing = Object.entries(facility.costs).find(([id, amount]) => held(id) < amount)
    if (missing) return { label: `升级${facility.name}缺${nameOf(missing[0])}`, panel: 'sect' }
  }
  const craftable = recipes.find(recipe => recipe.max_quantity > 0)
  if (craftable) return { label: `可炼${craftable.name}`, panel: craftable.kind === 'pill' ? 'alchemy' : 'forge' }
  return null
}