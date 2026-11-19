import * as THREE from 'three'
import { createCultivatorModel } from './characters/cultivatorModel'
import { battleImpact, type BattleEvent, type BattleUnit } from './battlePlayback'

export interface BattleSceneState {
  units: readonly BattleUnit[]
  event: BattleEvent | null
  phase: 'idle' | 'windup' | 'contact' | 'recover'
  playing: boolean
  reduced: boolean
}
export interface BattleSceneLabel { id: string; x: number; y: number; visible: boolean }

/** 双方前后三列站位；只决定画面位置，不参与服务端目标选择。 */
export function battlePosition(unit: Pick<BattleUnit, 'side' | 'slot'>) {
  const direction = unit.side === 'ally' ? -1 : 1
  return { x: direction * (3.2 + Math.floor(unit.slot / 3) * 2.5), z: (unit.slot % 3 - 1) * 2.6, facing: -direction * Math.PI / 2 }
}

export function createBattleScene(container: HTMLElement, options: {
  labels: (labels: BattleSceneLabel[]) => void
  select: (id: string) => void
  failure: () => void
}) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.domElement.setAttribute('aria-hidden', 'true')
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-11, 11, 7, -7, .1, 100)
  camera.position.set(6, 12, 20)
  camera.lookAt(0, .6, 0)
  const sun = new THREE.DirectionalLight('#fff0d1', 3.1)
  sun.position.set(-8, 16, 9)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  Object.assign(sun.shadow.camera, { left: -11, right: 11, top: 8, bottom: -8, near: 1, far: 40 })
  sun.shadow.normalBias = .035
  scene.add(sun, sun.target, new THREE.HemisphereLight('#eef5df', '#43544b', 2.1))
  const owned = new THREE.Group()
  scene.add(owned)
  const platform = new THREE.Mesh(new THREE.CylinderGeometry(8.8, 9, .32, 48), new THREE.MeshStandardMaterial({ color: '#d6d7bb', roughness: .95, flatShading: true }))
  platform.scale.z = .67
  platform.position.y = -.16
  platform.receiveShadow = true
  owned.add(platform)
  const ringMaterial = new THREE.MeshBasicMaterial({ color: '#9cae8f', transparent: true, opacity: .65, side: THREE.DoubleSide })
  for (const radius of [2.4, 5.3, 8.1]) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(radius, radius + .035, 48), ringMaterial)
    ring.rotation.x = -Math.PI / 2
    ring.scale.y = .67
    ring.position.y = .008
    owned.add(ring)
  }
  const models = new Map<string, { figure: ReturnType<typeof createCultivatorModel>; key: string }>()
  const effects = new THREE.Group()
  const effectGeometry = new THREE.TorusGeometry(.7, .045, 4, 22, Math.PI * 1.55)
  const effectMaterials = {
    hit: new THREE.MeshBasicMaterial({ color: '#f6db9a', transparent: true, opacity: .9 }),
    blocked: new THREE.MeshBasicMaterial({ color: '#9ac9d4', transparent: true, opacity: .8 }),
    healed: new THREE.MeshBasicMaterial({ color: '#93cba0', transparent: true, opacity: .8 }),
    guarded: new THREE.MeshBasicMaterial({ color: '#94bfcc', transparent: true, opacity: .8 }),
    empowered: new THREE.MeshBasicMaterial({ color: '#c7b77a', transparent: true, opacity: .8 }),
  }
  scene.add(effects)
  const raycaster = new THREE.Raycaster()
  const abort = new AbortController()
  let state: BattleSceneState = { units: [], event: null, phase: 'idle', playing: false, reduced: false }
  let frame = 0, disposed = false, interrupted = false, width = 1, height = 1, started = 0, impactStarted = 0
  let lastLabels = ''

  function draw(now: number) {
    frame = 0
    if (disposed || interrupted || document.hidden) return
    const elapsed = Math.max(0, now / 1000 - started)
    const actor = state.units.find(unit => unit.id === state.event?.actor_id)
    const damaged = state.event?.effects.find(effect => effect.kind === 'damage' && (effect.amount > 0 || effect.absorbed > 0))
    const target = state.units.find(unit => unit.id === damaged?.target_id)
    const melee = !!damaged && ['strike', 'slash', 'wave'].includes(state.event?.vfx ?? 'strike')
    for (const unit of state.units) {
      const model = models.get(unit.id)
      if (!model) continue
      const base = battlePosition(unit)
      const acting = state.playing && unit.id === actor?.id
      const unitEffects = state.event?.effects.filter(effect => effect.target_id === unit.id) ?? []
      const impact = state.playing && state.phase !== 'windup' ? battleImpact(unitEffects) : ''
      const contact = acting && target && melee
      let travel = 0
      if (contact) {
        if (state.phase === 'windup') travel = -.22 * Math.min(1, elapsed / .1)
        if (state.phase === 'contact') travel = 1.15
        if (state.phase === 'recover') travel = 1.15 * Math.max(0, 1 - elapsed / .22)
      }
      const toward = target ? battlePosition(target) : base
      const angle = Math.atan2(toward.x - base.x, toward.z - base.z)
      const recoil = impact === 'hit' && !state.reduced ? Math.sin(Math.min(1, elapsed / .16) * Math.PI) * .18 : 0
      model.figure.group.position.set(base.x + Math.sin(angle) * travel + (unit.side === 'ally' ? -recoil : recoil), .015, base.z + Math.cos(angle) * travel)
      model.figure.group.rotation.y = acting && target ? angle : base.facing
      model.figure.pose({ time: state.reduced ? 0 : now / 1000, phase: acting ? state.phase : 'idle', melee, hit: impact === 'hit', fallen: unit.hp <= 0 })
    }
    for (const ring of effects.children) {
      const progress = Math.min(1, Math.max(0, now / 1000 - impactStarted) / .36)
      ring.visible = !state.reduced && progress < 1
      ring.scale.setScalar(.65 + progress * .7)
      ring.rotation.z = progress * .8
    }
    try { renderer.render(scene, camera) }
    catch {
      interrupted = true
      options.failure()
      return
    }
    const labels = state.units.map(unit => {
      const model = models.get(unit.id)!.figure.group
      const point = model.position.clone().add(new THREE.Vector3(0, unit.hp > 0 ? 3 : .8, 0)).project(camera)
      return { id: unit.id, x: (point.x + 1) / 2 * width, y: (1 - point.y) / 2 * height, visible: Math.abs(point.x) < 1 && Math.abs(point.y) < 1 }
    })
    const key = JSON.stringify(labels)
    if (key !== lastLabels) { lastLabels = key; options.labels(labels) }
    if (state.playing && !state.reduced) request()
  }
  function request() { if (!disposed && !interrupted && !frame && !document.hidden) frame = requestAnimationFrame(draw) }
  function update(next: BattleSceneState) {
    if (disposed || interrupted) return
    if (next.phase !== state.phase || next.event !== state.event) started = performance.now() / 1000
    const wasLanded = state.playing && !state.reduced && state.phase !== 'windup'
    const landed = next.playing && !next.reduced && next.phase !== 'windup'
    const newImpact = landed && (!wasLanded || next.event !== state.event)
    state = next
    const present = new Set(next.units.map(unit => unit.id))
    for (const [id, model] of models) if (!present.has(id)) {
      scene.remove(model.figure.group); model.figure.dispose(); models.delete(id)
    }
    for (const unit of next.units) {
      const key = unit.template_id + ':' + unit.side
      let model = models.get(unit.id)
      if (model?.key !== key) {
        if (model) { scene.remove(model.figure.group); model.figure.dispose() }
        const figure = createCultivatorModel({ templateId: unit.template_id, enemy: unit.side === 'enemy', boss: unit.template_id.includes('master') })
        figure.group.userData.unitId = unit.id
        model = { figure, key }
        models.set(unit.id, model)
        scene.add(figure.group)
      }
    }
    if (!landed || newImpact) effects.clear()
    if (newImpact) impactStarted = performance.now() / 1000
    if (newImpact) for (const unit of next.units) {
      const kind = battleImpact(next.event?.effects.filter(effect => effect.target_id === unit.id) ?? [])
      if (!kind) continue
      const effect = new THREE.Mesh(effectGeometry, effectMaterials[kind])
      const base = battlePosition(unit)
      effect.position.set(base.x, 1.25, base.z)
      effect.rotation.y = Math.PI / 5
      if (kind === 'healed' || kind === 'empowered') { effect.rotation.x = -Math.PI / 2; effect.position.y = .2 }
      effects.add(effect)
    }
    request()
  }
  renderer.domElement.addEventListener('click', event => {
    if (disposed || interrupted) return
    const rect = renderer.domElement.getBoundingClientRect()
    raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2), camera)
    for (const hit of raycaster.intersectObjects([...models.values()].map(model => model.figure.group), true)) {
      let object: THREE.Object3D | null = hit.object
      while (object && !object.userData.unitId) object = object.parent
      if (object?.userData.unitId) { options.select(object.userData.unitId); break }
    }
  }, { signal: abort.signal })
  renderer.domElement.addEventListener('webglcontextlost', event => {
    event.preventDefault(); interrupted = true; cancelAnimationFrame(frame); frame = 0; options.failure()
  }, { signal: abort.signal })
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(frame); frame = 0 }
    else request()
  }, { signal: abort.signal })
  const observer = new ResizeObserver(() => {
    width = Math.max(1, container.clientWidth); height = Math.max(1, container.clientHeight)
    renderer.setSize(width, height)
    const vertical = Math.max(10.5, 21 / (width / height))
    camera.left = -vertical * width / height / 2; camera.right = -camera.left
    camera.top = vertical / 2; camera.bottom = -camera.top
    camera.updateProjectionMatrix(); camera.updateMatrixWorld()
    request()
  })
  container.appendChild(renderer.domElement)
  observer.observe(container)
  request()
  return { update, dispose() {
    if (disposed) return
    disposed = true
    abort.abort(); observer.disconnect(); cancelAnimationFrame(frame)
    for (const model of models.values()) model.figure.dispose()
    models.clear()
    const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>()
    owned.traverse(object => { if (object instanceof THREE.Mesh) { geometries.add(object.geometry); for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material) } })
    for (const geometry of geometries) geometry.dispose()
    for (const material of materials) material.dispose()
    effectGeometry.dispose()
    for (const material of Object.values(effectMaterials)) material.dispose()
    sun.shadow.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove()
  } }
}
