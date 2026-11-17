interface Point { x: number; y: number }
export interface SceneMotion { dx: number; dy: number; scale: number }

// 一次触摸序列中发生过拖动或双指操作，抬手就不能再解释成建筑点击。
export class SceneGestures {
  private points = new Map<number, Point>()
  private origin: Point | null = null
  private travelled = false

  start(id: number, x: number, y: number) {
    if (!this.points.size) { this.origin = { x, y }; this.travelled = false }
    this.points.set(id, { x, y })
    if (this.points.size > 1) this.travelled = true
  }

  move(id: number, x: number, y: number): SceneMotion | null {
    const previous = this.points.get(id)
    if (!previous) return null
    const before = [...this.points.values()]
    this.points.set(id, { x, y })
    const after = [...this.points.values()]
    if (this.origin && Math.hypot(x - this.origin.x, y - this.origin.y) > 6) this.travelled = true
    if (before.length === 2) {
      const a = before[0]!, b = before[1]!, c = after[0]!, d = after[1]!
      const distance = Math.hypot(a.x - b.x, a.y - b.y)
      return { dx: (c.x + d.x - a.x - b.x) / 2, dy: (c.y + d.y - a.y - b.y) / 2,
        scale: distance > 0 ? Math.hypot(c.x - d.x, c.y - d.y) / distance : 1 }
    }
    return { dx: x - previous.x, dy: y - previous.y, scale: 1 }
  }

  end(id: number): boolean {
    const tap = this.points.has(id) && this.points.size === 1 && !this.travelled
    this.points.delete(id)
    return tap
  }

  cancel() { this.points.clear(); this.origin = null; this.travelled = true }
}
