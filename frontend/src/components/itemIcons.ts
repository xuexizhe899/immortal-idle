// 与 config/recipes 和 config/materials 对齐；未知 ID 不发起请求，直接显示占位。
export const ITEM_ICON_IDS = new Set([
  'han_tie', 'jiao_gu', 'jiu_ye', 'ling_cao', 'xuan_jing', 'yun_mu',
  'gu_ti_dan', 'hui_ling_dan', 'ju_qi_dan', 'liao_shang_dan',
  'po_jing_dan', 'yang_shen_dan',
  'hu_xin_jing', 'ju_ling_pei', 'liu_yun_xue', 'po_mo_fu',
  'qing_feng_jian', 'xuan_tie_jia',
])

export function itemIconPath(id?: string | null): string {
  return id && ITEM_ICON_IDS.has(id) ? `/assets/items/${id}.svg` : ''
}
