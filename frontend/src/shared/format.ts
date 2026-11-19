// 只处理与游戏含义无关的数值展示，供文案、资源栏和战报共用。
export function number(value: number | undefined, digits = 0): string {
  return (value ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: digits })
}

export function durationFromHours(hours: number | undefined): string {
  const seconds = Math.round(Math.max(0, hours ?? 0) * 3600)
  const wholeHours = Math.floor(seconds / 3600)
  const minutes = Math.floor(seconds % 3600 / 60)
  if (wholeHours) return `${number(wholeHours)} 小时${minutes ? ` ${minutes} 分钟` : ''}`
  if (minutes) return `${minutes} 分钟${seconds % 60 ? ` ${seconds % 60} 秒` : ''}`
  return seconds ? `${seconds} 秒` : (hours ?? 0) > 0 ? '不足 1 秒' : '0 秒'
}
