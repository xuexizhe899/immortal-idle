import * as THREE from 'three'
import { buildCityEnvironment, CITY_WORLD_SCALE } from './cityBuildings'
import { CITY_BUILDINGS, CITY_PLAZA, clampCityCamera, type CityActor, type CameraPose } from './cityModel'
import { sampleCityMotion } from './cityMotion'
import { createCityActors } from './pixelSprites'
import { createScenePost } from './postprocessing'
import { SceneGestures } from './sceneGestures'

export interface SceneLabel { id: string; x: number; y: number; visible: boolean }
export interface SceneLighting { brightness: number; saturation: number; night: number; warmth: number }
interface SceneOptions {
  select: (kind: 'building' | 'disciple', id: string) => void
  labels: (items: SceneLabel[]) => void
  imageFailure: () => void
  contextLost: () => void
}

export function createCityScene(container: HTMLElement, options: SceneOptions) {
  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'default' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, matchMedia('(pointer: coarse)').matches ? 1.25 : 1.75))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.outputColorSpace = THREE.SRGBColorSpace
  const canvas = renderer.domElement
  canvas.setAttribute('aria-hidden', 'true')
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-25, 25, 18, -18, .1, 150)
  const sun = new THREE.DirectionalLight('#fff1d1', 2.7)
  sun.position.set(-22, 35, 15)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  Object.assign(sun.shadow.camera, { left: -32, right: 32, top: 29, bottom: -29, near: 1, far: 100 })
  sun.shadow.normalBias = .05
  scene.add(sun, sun.target)
  const sky = new THREE.HemisphereLight('#e5f0df', '#344a44', 2.1)
  scene.add(sky)
  let world: ReturnType<typeof buildCityEnvironment>
  try { world = buildCityEnvironment() }
  catch (error) { renderer.dispose(); renderer.forceContextLoss(); throw error }
  world.group.scale.setScalar(CITY_WORLD_SCALE)
  for (const [id, building] of world.buildings) building.userData = { kind: 'building', id }
  scene.add(world.group)
  world.group.updateMatrixWorld(true)
  const sprites = createCityActors()
  sprites.group.scale.setScalar(CITY_WORLD_SCALE)
  scene.add(sprites.group)
  const post = createScenePost()
  const gestures = new SceneGestures()
  const abort = new AbortController()
  const raycaster = new THREE.Raycaster()
  const groundRay = new THREE.Raycaster(new THREE.Vector3(), new THREE.Vector3(0, -1, 0), .001, 3 * CITY_WORLD_SCALE)
  const center = new THREE.Vector3()
  let pose: CameraPose = { x: 0, z: 0, zoom: 1.15 }
  let width = 1, height = 1, frame = 0, disposed = false, interrupted = false, reduced = false, depth = false
  let actorData: CityActor[] = []
  let motionSeconds = 0, lastDraw: number | undefined
  const groundHeights = new Map<string, { x: number; z: number; height: number }>()
  let lastLabels = ''

  function updateCamera() {
    // 先保留开阔城心的近景，外围建筑通过拖动巡视。
    const span = Math.max(35, 43 * height / width)
    camera.left = -span * width / height / 2
    camera.right = -camera.left
    camera.top = span / 2; camera.bottom = -span / 2
    center.set(pose.x, 0, pose.z)
    // 固定方位和俯角；镜头仅平移与缩放，人物保持自身的世界朝向。
    camera.position.copy(center).add(new THREE.Vector3(27, 32, 38))
    camera.lookAt(center)
    const upY = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion).y
    const minimumZoom = Math.max(.75, span * upY / (2 * (camera.position.y + 0.08 * CITY_WORLD_SCALE)))
    pose = clampCityCamera(pose, minimumZoom)
    camera.zoom = pose.zoom
    camera.updateProjectionMatrix(); camera.updateMatrixWorld()
    request()
  }

  function labels() {
    const items = CITY_BUILDINGS.map(building => {
      const point = new THREE.Vector3(building.x * CITY_WORLD_SCALE, 1.4 * CITY_WORLD_SCALE,
        (building.z + building.depth / 2 + .6) * CITY_WORLD_SCALE).project(camera)
      return { id: building.id, x: (point.x + 1) * width / 2, y: (1 - point.y) * height / 2,
        visible: point.z >= -1 && point.z <= 1 && Math.abs(point.x) < 1.1 && Math.abs(point.y) < 1.1 }
    })
    const key = JSON.stringify(items)
    if (key !== lastLabels) { lastLabels = key; options.labels(items) }
  }

  function draw(now: number) {
    frame = 0
    if (disposed || interrupted || document.hidden) return
    if (!reduced && lastDraw !== undefined) motionSeconds += Math.min(.05, Math.max(0, (now - lastDraw) / 1000))
    lastDraw = reduced ? undefined : now
    for (const actor of actorData) {
      const position = sampleCityMotion(actor, motionSeconds, reduced)
      let ground = groundHeights.get(actor.id)
      if (!ground || ground.x !== position.x || ground.z !== position.z) {
        ground = { x: position.x, z: position.z, height: groundAt(position.x, position.z) }
        groundHeights.set(actor.id, ground)
      }
      sprites.move(actor.id, position, ground.height, motionSeconds)
    }
    if (depth) post.render(renderer, scene, camera, center)
    else renderer.render(scene, camera)
    labels()
    if (!reduced) request()
  }
  function request() { if (!disposed && !interrupted && !frame && !document.hidden) frame = requestAnimationFrame(draw) }

  function groundAt(x: number, z: number) {
    // 采样当前位置的台面，人物与阴影共用高度，走过广场纹章时仍贴地。
    groundRay.ray.origin.set(x * CITY_WORLD_SCALE, 2 * CITY_WORLD_SCALE, z * CITY_WORLD_SCALE)
    const inPlaza = Math.abs(x - CITY_PLAZA.x) <= CITY_PLAZA.width / 2 && Math.abs(z - CITY_PLAZA.z) <= CITY_PLAZA.depth / 2
    const hits = inPlaza ? groundRay.intersectObjects(world.plazaSurfaces) : groundRay.intersectObject(world.group, true)
    return (hits[0]?.point.y ?? .04) / CITY_WORLD_SCALE
  }

  function pan(dx: number, dy: number) {
    const unit = (camera.top - camera.bottom) / height / pose.zoom
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0)
    const forward = new THREE.Vector3(right.z, 0, -right.x)
    const movement = right.multiplyScalar(-dx * unit).add(forward.multiplyScalar(dy * unit / .65))
    pose = clampCityCamera({ ...pose, x: pose.x + movement.x, z: pose.z + movement.z })
    updateCamera()
  }
  function zoom(scale: number) { pose = clampCityCamera({ ...pose, zoom: pose.zoom * scale }); updateCamera() }

  function pick(event: PointerEvent) {
    const rect = canvas.getBoundingClientRect()
    raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1,
      1 - (event.clientY - rect.top) / rect.height * 2), camera)
    // 人物与建筑共用真实几何深度，身体之外的空隙不会被矩形立牌截获。
    const hits = raycaster.intersectObjects([world.group, sprites.group], true)
    for (const hit of hits) {
      let object: THREE.Object3D | null = hit.object
      while (object && !object.userData.kind) object = object.parent
      if (object?.userData.kind) { options.select(object.userData.kind, object.userData.id); return }
      // 接地阴影已排除射线；实体地形与建筑装饰会挡住其后的目标。
      return
    }
  }
  const listen = { signal: abort.signal }
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return
    canvas.setPointerCapture(event.pointerId)
    gestures.start(event.pointerId, event.clientX, event.clientY)
    container.focus({ preventScroll: true })
  }, listen)
  canvas.addEventListener('pointermove', event => {
    const motion = gestures.move(event.pointerId, event.clientX, event.clientY)
    if (motion) { pan(motion.dx, motion.dy); zoom(motion.scale) }
  }, listen)
  canvas.addEventListener('pointerup', event => { if (gestures.end(event.pointerId)) pick(event) }, listen)
  canvas.addEventListener('pointercancel', () => gestures.cancel(), listen)
  canvas.addEventListener('lostpointercapture', event => { gestures.end(event.pointerId) }, listen)
  canvas.addEventListener('wheel', event => { event.preventDefault(); zoom(Math.exp(-event.deltaY * .001)) }, { ...listen, passive: false })
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault(); interrupted = true; cancelAnimationFrame(frame); frame = 0; gestures.cancel()
    options.contextLost()
  }, listen)
  container.addEventListener('keydown', event => {
    if (event.target !== container) return
    const direction: Record<string, [number, number]> = { ArrowLeft: [55, 0], ArrowRight: [-55, 0], ArrowUp: [0, 55], ArrowDown: [0, -55] }
    if (direction[event.key]) { event.preventDefault(); pan(...direction[event.key]!) }
    else if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(1.15) }
    else if (event.key === '-') { event.preventDefault(); zoom(1 / 1.15) }
    else if (event.key === 'Home') { event.preventDefault(); reset() }
  }, listen)
  document.addEventListener('visibilitychange', () => {
    lastDraw = undefined
    if (document.hidden) { cancelAnimationFrame(frame); frame = 0; gestures.cancel() }
    else request()
  }, listen)
  const observer = new ResizeObserver(() => {
    width = Math.max(1, container.clientWidth); height = Math.max(1, container.clientHeight)
    renderer.setSize(width, height)
    const size = renderer.getDrawingBufferSize(new THREE.Vector2())
    post.resize(size.x, size.y)
    updateCamera()
  })
  container.append(canvas)
  observer.observe(container)
  updateCamera()

  function reset() { pose = { x: 0, z: 0, zoom: 1.15 }; updateCamera() }
  return {
    updateActors(actors: CityActor[]) {
      actorData = actors
      groundHeights.clear()
      sprites.sync(actors, groundAt)
      request()
    },
    updateLighting(light: SceneLighting) {
      const night = light.night / .62
      scene.background = new THREE.Color('#c5d5c4').lerp(new THREE.Color('#203d51'), night)
      scene.fog = new THREE.Fog(scene.background, 63, 100)
      canvas.style.filter = `brightness(${light.brightness}) saturate(${light.saturation})`
      sun.intensity = 2.7 - night * 2.15
      sun.color.set(light.warmth > .2 ? '#ffd0a0' : '#fff1d1')
      sky.intensity = 2.1 - night * 1.15
      sky.color.set(night > .5 ? '#a2b8d6' : '#e5f0df')
      for (const lamp of world.lamps) {
        const material = lamp.material as THREE.MeshStandardMaterial
        material.emissiveIntensity = .4 + night * 2
      }
      request()
    },
    setPreferences(preferences: { reduced: boolean; depth: boolean }) {
      reduced = preferences.reduced; depth = preferences.depth; lastDraw = undefined; request()
    },
    reset,
    zoom,
    dispose() {
      if (disposed) return
      disposed = true; cancelAnimationFrame(frame); observer.disconnect(); abort.abort(); gestures.cancel()
      groundHeights.clear()
      sprites.dispose(); world.dispose(); post.dispose()
      sun.shadow.dispose(); renderer.dispose(); renderer.forceContextLoss(); canvas.remove()
    },
  }
}
