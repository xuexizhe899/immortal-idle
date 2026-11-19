import * as THREE from 'three'
import { createCultivatorModel } from '../characters/cultivatorModel'
import type { CityActor } from './cityModel'
import type { CityMotionPose } from './cityMotion'

/*!
 * Required Notice: Copyright 2026 mewamew and contributors. https://github.com/mewamew/my_ai_town
 * PolyForm Noncommercial 1.0.0: https://polyformproject.org/licenses/noncommercial/1.0.0
 */
// Historical standee adaptation and required notice: licenses/my_ai_town/SOURCE.md.

export function createCityActors() {
  const group = new THREE.Group()
  const actors = new Map<string, THREE.Group>()
  const models = new Map<string, { templateId: string; model: ReturnType<typeof createCultivatorModel> }>()
  const shadows = new Map<string, THREE.Mesh>()
  const shadowGeometry = new THREE.CircleGeometry(.48, 16)
  const shadowMaterial = new THREE.MeshBasicMaterial({ color: '#223e35', transparent: true, opacity: .2, depthWrite: false })
  let disposed = false

  function remove(id: string) {
    const entry = models.get(id)
    if (!entry) return
    group.remove(entry.model.group)
    entry.model.dispose()
    models.delete(id)
    actors.delete(id)
    const shadow = shadows.get(id)
    if (shadow) group.remove(shadow)
    shadows.delete(id)
  }

  function sync(items: CityActor[], groundAt: (x: number, z: number) => number = () => .015) {
    if (disposed) return
    const current = new Map(items.map(actor => [actor.id, actor]))
    for (const [id, entry] of models) {
      if (current.get(id)?.templateId !== entry.templateId) remove(id)
    }
    for (const actor of items) {
      let entry = models.get(actor.id)
      if (!entry) {
        const model = createCultivatorModel({ templateId: actor.templateId })
        entry = { templateId: actor.templateId, model }
        models.set(actor.id, entry)
        actors.set(actor.id, model.group)
        group.add(model.group)
        const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial)
        shadow.rotation.x = -Math.PI / 2
        shadow.scale.y = .5
        shadow.userData.groundShadow = true
        // 接地阴影没有实体体积，不拦截射向人物或地面的点选。
        shadow.raycast = () => {}
        group.add(shadow)
        shadows.set(actor.id, shadow)
      }
      const groundY = groundAt(actor.x, actor.z)
      entry.model.group.position.set(actor.x, groundY, actor.z)
      entry.model.group.userData = { kind: 'disciple', id: actor.id, groundY }
      entry.model.pose({ time: 0, walking: false })
      shadows.get(actor.id)!.position.set(actor.x, groundY + .012, actor.z)
    }
  }

  function move(id: string, pose: CityMotionPose, groundY: number, seconds: number) {
    const entry = models.get(id)
    if (!entry) return
    const root = entry.model.group
    root.position.set(pose.x, groundY, pose.z)
    root.rotation.y = pose.heading
    root.userData.groundY = groundY
    // 根节点保持脚底贴地；转身跟随路径，步态仅驱动模型内部关节。
    entry.model.pose({ time: pose.moving ? seconds : 0, walking: pose.moving })
    shadows.get(id)!.position.set(pose.x, groundY + .012, pose.z)
  }

  return { group, actors, sync, move, dispose() {
    if (disposed) return
    disposed = true
    for (const id of models.keys()) remove(id)
    shadowGeometry.dispose()
    shadowMaterial.dispose()
    group.clear()
  } }
}
