import type { Catalog } from '../api/client'

// 运行资源统一放在 public/assets；配置只保存资源键或站内 URL，版本目录与扩展名在这里补齐。
const ASSET_ROOT = '/assets'
const IMAGE_EXTENSION = /\.(?:png|jpe?g|webp|svg)$/i

// 人物 asset_id 约定为不带扩展名的 PNG 键（如 trial-v03/zhugeliang）；
// 已是站内 URL 的输入原样返回，键自带扩展名时不再重复拼接。
export function characterImage(asset?: string | null): string {
  const value = asset?.trim()
  if (!value) return ''
  if (value.startsWith('/')) return value
  return `${ASSET_ROOT}/${value}${IMAGE_EXTENSION.test(value) ? '' : '.png'}`
}

// 宗门、图鉴按当前 catalog 取立绘；模板缺失时以模板 ID 作旧版根目录资源键。
export function discipleImage(templateId: string, catalog?: Catalog | null): string {
  return characterImage(catalog?.disciples[templateId]?.asset_id ?? templateId)
}

// 出征以出发时固化的 asset_id 为准，只有旧档快照缺该字段时才回退当前 catalog。
export function snapshotDiscipleImage(assetId: string | undefined, templateId: string, catalog?: Catalog | null): string {
  return characterImage(assetId || catalog?.disciples[templateId]?.asset_id || templateId)
}

// 场景与建筑配置已是带扩展名的站内 URL；无前导斜杠时视为 public/assets 下的键。
export function sceneImage(source?: string | null): string {
  const value = source?.trim()
  if (!value) return ''
  return value.startsWith('/') ? value : `${ASSET_ROOT}/${value}`
}

export const TOWER_SCENE_IMAGE = sceneImage('trial-v03/scene_tower_trial.png')
export const TOWER_SPRITE_IMAGE = sceneImage('buildings/sprite_tower.png')

// 与 config/recipes 和 config/materials 对齐；未知 ID 不发起请求，直接显示占位。
export const ITEM_ICON_IDS = new Set([
  'han_tie', 'jiao_gu', 'jiu_ye', 'ling_cao', 'xuan_jing', 'yun_mu',
  'ling_mu', 'qing_shi', 'chi_tong', 'yao_shou_pi',
  'gong_fa_qi_pei', 'hu_chi_qi_pei', 'po_jing_ling_cai',
  'gu_ti_dan', 'hui_ling_dan', 'ju_qi_dan', 'liao_shang_dan',
  'po_jing_dan', 'yang_shen_dan',
  'hu_xin_jing', 'ju_ling_pei', 'liu_yun_xue', 'po_mo_fu',
  'qing_feng_jian', 'xuan_tie_jia',
  'qinglong_yanyuedao', 'zhangba_shemao', 'qingnang_yaoxiang', 'baiyu_shan',
  'longdan_liangyinqiang', 'sheri_shengong', 'yuehua_yulun', 'suxin_yusan',
  'liquan_shenqiang', 'huo_jian_qiang', 'sanjian_liangrendao', 'chibi_jiaowei_qin',
  'huntian_yi', 'qinglian_jian', 'shisheng_shujuan', 'xianshi_lingyu',
])

export function itemIconPath(id?: string | null): string {
  return id && ITEM_ICON_IDS.has(id) ? `${ASSET_ROOT}/items/${id}.svg` : ''
}

// 三件既有物品先接入精修试稿；关羽专武只作审阅概念，不进入可用物品注册表。
const ITEM_ARTWORK_IDS = new Set(['liao_shang_dan', 'po_jing_dan', 'qing_feng_jian'])

export function itemArtworkPath(id?: string | null, variant: 'icon' | 'display' = 'icon'): string {
  if (!id || !ITEM_ARTWORK_IDS.has(id)) return itemIconPath(id)
  return `${ASSET_ROOT}/art-foundation/items/${id}${variant === 'display' ? '_display' : ''}.svg`
}

// 资源登记不等于敌人已加入遭遇；新增六种形象先作美术储备，战斗定义仍来自服务端。
const ENEMY_ARTWORK_IDS = new Set([
  'stone_guard', 'cloud_archer', 'jade_warden', 'tower_master',
  'cinder_blade', 'bamboo_swordsman', 'frost_crane',
  'vine_spirit', 'bronze_beast', 'lantern_wraith',
])

// 战报优先使用固化的敌方立绘；旧快照缺少图片键时保留原模板图与未知占位。
export function enemyImage(templateId: string, assetId?: string | null): string {
  return characterImage(assetId) || (ENEMY_ARTWORK_IDS.has(templateId) ? `${ASSET_ROOT}/art-foundation/enemies/${templateId}.png` : '')
}
