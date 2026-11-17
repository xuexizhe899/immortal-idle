import * as THREE from 'three'
import type { CityActor } from './cityModel'

/*!
 * Required Notice: Copyright 2026 mewamew and contributors. https://github.com/mewamew/my_ai_town
 * PolyForm Noncommercial 1.0.0: https://polyformproject.org/licenses/noncommercial/1.0.0
 */
// Adapted from my_ai_town standee.ts at 5ddc1a3 (PolyForm Noncommercial 1.0.0).
// Source, changes and required notice: licenses/my_ai_town/SOURCE.md.
const uprightDepth = `
  vec4 foot = viewMatrix * modelMatrix * vec4(transformed.x, 0.0, 0.0, 1.0);
  vec3 up = (viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz;
  float rise = length((modelMatrix * vec4(0.0, transformed.y, 0.0, 0.0)).xyz);
  foot.z += rise * up.z / max(abs(up.y), 0.2);
  vec4 clip = projectionMatrix * foot;
  gl_Position.z = clip.z / clip.w * gl_Position.w;
`

export function createCityActors(onImageFailure: () => void, onImageLoaded: () => void) {
  const group = new THREE.Group()
  const textures = new Map<string, THREE.Texture>()
  const masks = new Map<THREE.Texture, { width: number; height: number; alpha: Uint8Array }>()
  const actors = new Map<string, THREE.Mesh<THREE.PlaneGeometry, THREE.MeshLambertMaterial>>()
  const loader = new THREE.TextureLoader()
  let disposed = false
  const shadows = new Map<string, THREE.Mesh>()
  const shadowGeometry = new THREE.CircleGeometry(.48, 16)
  const shadowMaterial = new THREE.MeshBasicMaterial({ color: '#223e35', transparent: true, opacity: .2, depthWrite: false })

  function sync(items: CityActor[], camera: THREE.Camera, groundAt: (x: number, z: number) => number = () => .015) {
    for (const mesh of actors.values()) { mesh.geometry.dispose(); mesh.material.dispose(); group.remove(mesh) }
    actors.clear()
    for (const shadow of shadows.values()) group.remove(shadow)
    shadows.clear()
    for (const actor of items) {
      if (!actor.image) continue
      let texture = textures.get(actor.image)
      if (!texture) {
        texture = loader.load(actor.image, loaded => {
          if (disposed) return
          const image = loaded.image as HTMLImageElement
          const canvas = document.createElement('canvas')
          canvas.width = image.width; canvas.height = image.height
          const context = canvas.getContext('2d')!
          context.drawImage(image, 0, 0)
          const pixels = context.getImageData(0, 0, image.width, image.height).data
          const alpha = new Uint8Array(image.width * image.height)
          for (let index = 0; index < alpha.length; index++) alpha[index] = pixels[index * 4 + 3]!
          masks.set(loaded, { width: image.width, height: image.height, alpha })
          // 保留单幅人物的原始比例，脚底锚点不随长武器宽度偏移。
          for (const mesh of actors.values()) if (mesh.material.map === loaded) {
            mesh.scale.x = image.width / image.height * 2.7
          }
          onImageLoaded()
        }, undefined, () => { if (!disposed) onImageFailure() })
        texture.colorSpace = THREE.SRGBColorSpace
        texture.magFilter = THREE.NearestFilter
        texture.minFilter = THREE.LinearFilter
        textures.set(actor.image, texture)
      }
      const material = new THREE.MeshLambertMaterial({ map: texture, alphaTest: .4, side: THREE.DoubleSide,
        color: actor.injured ? '#ddd5c4' : '#ffffff' })
      material.onBeforeCompile = shader => {
        shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>\n${uprightDepth}`)
      }
      const geometry = new THREE.PlaneGeometry(1, 2.7)
      geometry.translate(0, 1.35, 0)
      const mesh = new THREE.Mesh(geometry, material)
      const image = texture.image as HTMLImageElement | undefined
      mesh.scale.x = image?.height ? image.width / image.height * 2.7 : 1.3
      const groundY = groundAt(actor.x, actor.z)
      mesh.position.set(actor.x, groundY + .025, actor.z)
      mesh.quaternion.copy(camera.quaternion)
      mesh.userData = { kind: 'disciple', id: actor.id, groundY: groundY + .025 }
      actors.set(actor.id, mesh)
      group.add(mesh)
      const shadow = new THREE.Mesh(shadowGeometry, shadowMaterial)
      shadow.rotation.x = -Math.PI / 2
      shadow.scale.y = .5
      shadow.position.set(actor.x, groundY + .012, actor.z)
      group.add(shadow)
      shadows.set(actor.id, shadow)
    }
  }

  function move(id: string, pose: { x: number; z: number; bob: number }, groundY: number) {
    const mesh = actors.get(id)
    if (!mesh) return
    mesh.position.set(pose.x, groundY + .025 + pose.bob, pose.z)
    mesh.userData.groundY = groundY + .025
    // 脚步起伏只作用于立牌，阴影继续落在移动位置的实际地表。
    shadows.get(id)!.position.set(pose.x, groundY + .012, pose.z)
  }

  function hitDepth(hit: THREE.Intersection, camera: THREE.Camera) {
    const mesh = actors.get(hit.object.userData.id)
    if (!mesh || mesh !== hit.object || !hit.uv) return null
    const mask = masks.get(mesh.material.map!)
    if (!mask) return null
    const x = Math.min(mask.width - 1, Math.max(0, Math.floor(hit.uv.x * mask.width)))
    const y = Math.min(mask.height - 1, Math.max(0, Math.floor((1 - hit.uv.y) * mask.height)))
    // 射线默认命中整张矩形，透明区域必须继续寻找后方目标。
    if (mask.alpha[y * mask.width + x]! < .4 * 255) return null
    const local = mesh.worldToLocal(hit.point.clone())
    const foot = new THREE.Vector3(local.x, 0, 0).applyMatrix4(mesh.matrixWorld).applyMatrix4(camera.matrixWorldInverse)
    const up = new THREE.Vector3(0, 1, 0).transformDirection(camera.matrixWorldInverse)
    const rise = new THREE.Vector3().setFromMatrixColumn(mesh.matrixWorld, 1).multiplyScalar(local.y).length()
    // 与 uprightDepth 同一投影，拾取顺序跟随画面中的站立深度。
    return -(foot.z + rise * up.z / Math.max(Math.abs(up.y), .2))
  }

  return { group, actors, sync, move, hitDepth, dispose() {
    disposed = true
    for (const mesh of actors.values()) { mesh.geometry.dispose(); mesh.material.dispose() }
    for (const texture of textures.values()) texture.dispose()
    shadowGeometry.dispose(); shadowMaterial.dispose()
    actors.clear(); shadows.clear(); textures.clear(); masks.clear(); group.clear()
  } }
}
