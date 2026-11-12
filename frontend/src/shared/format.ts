// 只处理与游戏含义无关的数值展示，供文案、资源栏和战报共用。
export function number(value: number | undefined, digits = 0): string {
  return (value ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: digits })
}