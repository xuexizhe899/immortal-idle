import type { CityActor } from './cityModel'

export interface CityMotionPose { x: number; z: number; bob: number; moving: boolean }

/** 常驻弟子沿广场短路停走；时钟和身份只决定演出，不改变值守或出征。 */
export function sampleCityMotion(actor: CityActor, seconds: number, reduced = false): CityMotionPose {
  const still = { x: actor.x, z: actor.z, bob: 0, moving: false }
  if (reduced || actor.duty || actor.injured) return still
  let seed = 0
  for (const letter of actor.id) seed = (Math.imul(seed, 31) + letter.charCodeAt(0)) >>> 0
  const direction = actor.x > 0 ? -1 : 1
  const points = [[actor.x, actor.z], [actor.x + direction * 3.6, actor.z],
    [actor.x + direction * 3.6, actor.z + 2], [actor.x, actor.z + 2]] as const
  const speed = .55 + seed % 3 * .08
  const pause = 1.6 + seed % 5 * .45
  const period = 11.2 / speed + pause * 4
  let time = (Math.max(0, seconds) + seed % 100 / 100 * period) % period
  for (let index = 0; index < points.length; index++) {
    const start = points[index]!, end = points[(index + 1) % points.length]!
    if (time < pause) return { ...still, x: start[0], z: start[1] }
    time -= pause
    const distance = Math.hypot(end[0] - start[0], end[1] - start[1])
    const duration = distance / speed
    if (time < duration) {
      const fraction = time / duration
      return { x: start[0] + (end[0] - start[0]) * fraction, z: start[1] + (end[1] - start[1]) * fraction,
        bob: Math.abs(Math.sin(time * speed * Math.PI * 2 / .75)) * .035, moving: true }
    }
    time -= duration
  }
  return still
}
