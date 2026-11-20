import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'

type Garment = 'robe' | 'dress' | 'armor' | 'short'
type Headdress = 'crown' | 'cap' | 'wrap' | 'bun' | 'doubleBun' | 'helmet' | 'loose'
type Prop = 'fan' | 'guandao' | 'moon' | 'parasol' | 'scroll' | 'bow' | 'herbs' | 'stones' | 'sword' | 'spear' | 'trident' | 'serpent' | 'armillary'
type Beard = 'none' | 'short' | 'long' | 'white' | 'wild'
type Profile = {
  cloth: string; lining: string; trim: string; metal: string; skin?: string
  garment: Garment; hat: Headdress; prop: Prop; beard?: Beard
  female?: boolean; broad?: boolean; cape?: string; hair?: string
}
type Point = [number, number, number]
type Surface = THREE.MeshStandardMaterial
type Limb = { upper: THREE.Group; lower: THREE.Group; end: THREE.Group }
type ClothJoint = { joint: THREE.Group; side: number; back: boolean }

// 身份锚点沿用 trial-v03 正式人物说明；这里只保存造型与用色，不复制 catalog 玩法定义。
const profiles: Record<string, Profile> = {
  zhugeliang: { cloth: '#476e57', lining: '#e5dfca', trim: '#b89a61', metal: '#889a92', garment: 'robe', hat: 'crown', prop: 'fan', beard: 'long' },
  guanyu: { cloth: '#406348', lining: '#d4cfb5', trim: '#a98b4c', metal: '#344e4b', skin: '#ad6e53', garment: 'armor', hat: 'cap', prop: 'guandao', beard: 'long', broad: true },
  change: { cloth: '#e4e1d3', lining: '#a8c0c2', trim: '#bba674', metal: '#b6c6c7', garment: 'dress', hat: 'bun', prop: 'moon', female: true },
  baisuzhen: { cloth: '#e9e6d8', lining: '#acc4b2', trim: '#789b82', metal: '#b7c6bd', garment: 'dress', hat: 'loose', prop: 'parasol', female: true },
  dufu: { cloth: '#687d80', lining: '#c5c6b5', trim: '#8c795b', metal: '#7f8983', garment: 'robe', hat: 'wrap', prop: 'scroll', beard: 'short', hair: '#70736c' },
  houyi: { cloth: '#526c63', lining: '#c6b997', trim: '#a58a51', metal: '#7c7151', garment: 'armor', hat: 'bun', prop: 'bow' },
  huatuo: { cloth: '#9cae99', lining: '#e7e1cb', trim: '#8c7755', metal: '#8e9a8c', garment: 'robe', hat: 'wrap', prop: 'herbs', beard: 'white', hair: '#d2d2bf' },
  jingwei: { cloth: '#d5c7a3', lining: '#5e8176', trim: '#ac8d4f', metal: '#8c9a87', garment: 'dress', hat: 'loose', prop: 'stones', female: true },
  libai: { cloth: '#dfdfd0', lining: '#64758b', trim: '#9e8b60', metal: '#a9bbbc', garment: 'robe', hat: 'loose', prop: 'sword', beard: 'short' },
  nezha: { cloth: '#ddd5ba', lining: '#8e4f42', trim: '#b79a50', metal: '#aa9264', garment: 'short', hat: 'doubleBun', prop: 'spear' },
  yangjian: { cloth: '#c9d5d0', lining: '#3f6263', trim: '#a89765', metal: '#aebdbb', garment: 'armor', hat: 'crown', prop: 'trident', cape: '#dfdfcf' },
  yuefei: { cloth: '#45524e', lining: '#a29c83', trim: '#9f8755', metal: '#4a5552', garment: 'armor', hat: 'helmet', prop: 'spear', beard: 'short', broad: true, cape: '#88584c' },
  zhangfei: { cloth: '#625b46', lining: '#8b5645', trim: '#9b8054', metal: '#424d49', garment: 'armor', hat: 'bun', prop: 'serpent', beard: 'wild', broad: true },
  zhangheng: { cloth: '#465c78', lining: '#b1b6af', trim: '#ad8e52', metal: '#9b895a', garment: 'robe', hat: 'cap', prop: 'armillary', beard: 'short' },
  zhaoyun: { cloth: '#d0dcd9', lining: '#a7bfc4', trim: '#b3ad8c', metal: '#bccbcb', garment: 'armor', hat: 'helmet', prop: 'spear', cape: '#e4e5d8' },
  zhouyu: { cloth: '#80564f', lining: '#d7d5be', trim: '#af955f', metal: '#3c5c5a', garment: 'armor', hat: 'cap', prop: 'fan' },
}
const wanderer: Profile = { cloth: '#d7d8c5', lining: '#557569', trim: '#a38f60', metal: '#a3b6b2', garment: 'robe', hat: 'bun', prop: 'sword' }
const guard: Profile = { cloth: '#53635b', lining: '#a3a18b', trim: '#9d8253', metal: '#53615e', garment: 'armor', hat: 'helmet', prop: 'spear' }
const sectMaster: Profile = { cloth: '#405d59', lining: '#d7d0b5', trim: '#b49a5a', metal: '#6d7d78', garment: 'armor', hat: 'crown', prop: 'sword', beard: 'long', broad: true, cape: '#81704f' }

function createMeshKit() {
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Map<string, Surface>()
  function own<T extends THREE.BufferGeometry>(geometry: T) { geometries.add(geometry); return geometry }
  const cube = own(new RoundedBoxGeometry(1, 1, 1, 2, .035))
  // 角色近景会直接暴露轮廓；提高基础曲面分段并使用平滑法线，避免脸、袖口和护具出现积木式折面。
  const sphere = own(new THREE.SphereGeometry(1, 16, 10))
  const cylinder = own(new THREE.CylinderGeometry(1, 1, 1, 12))
  function material(color: string, metal = false) {
    const key = `${color}:${metal}`
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({
      color,
      roughness: metal ? .48 : .86,
      metalness: metal ? .52 : 0,
      flatShading: false,
    }))
    return materials.get(key)!
  }
  function mesh(parent: THREE.Object3D, geometry: THREE.BufferGeometry, surface: Surface, position: Point = [0, 0, 0], scale: Point = [1, 1, 1]) {
    const part = new THREE.Mesh(geometry, surface)
    part.position.set(...position); part.scale.set(...scale)
    part.castShadow = true; part.receiveShadow = true
    parent.add(part)
    return part
  }
  function box(parent: THREE.Object3D, size: Point, position: Point, surface: Surface) { return mesh(parent, cube, surface, position, size) }
  function oval(parent: THREE.Object3D, size: Point, position: Point, surface: Surface) { return mesh(parent, sphere, surface, position, size) }
  function pole(parent: THREE.Object3D, radius: number, length: number, position: Point, surface: Surface) { return mesh(parent, cylinder, surface, position, [radius, length, radius]) }
  function taper(parent: THREE.Object3D, top: number, bottom: number, height: number, position: Point, surface: Surface, depth = 1) {
    return mesh(parent, own(new THREE.CylinderGeometry(top, bottom, height, 12)), surface, position, [1, 1, depth])
  }
  function solid(parent: THREE.Object3D, points: [number, number][], depth: number, position: Point, surface: Surface) {
    const outline = new THREE.Shape()
    points.forEach(([x, y], index) => index ? outline.lineTo(x, y) : outline.moveTo(x, y)); outline.closePath()
    const geometry = own(new THREE.ExtrudeGeometry(outline, {
      depth,
      bevelEnabled: true,
      bevelSegments: 2,
      bevelSize: Math.min(depth * .22, .012),
      bevelThickness: Math.min(depth * .16, .008),
    }))
    geometry.translate(0, 0, -depth / 2)
    return mesh(parent, geometry, surface, position)
  }
  function between(parent: THREE.Object3D, a: Point, b: Point, radius: number, surface: Surface) {
    const start = new THREE.Vector3(...a); const end = new THREE.Vector3(...b)
    const part = pole(parent, radius, start.distanceTo(end), [0, 0, 0], surface)
    part.position.copy(start.add(end).multiplyScalar(.5))
    part.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.sub(new THREE.Vector3(...a)).normalize())
    return part
  }
  return { own, mesh, box, oval, pole, taper, solid, between, material, materials, geometries }
}
type MeshKit = ReturnType<typeof createMeshKit>

function mergeStaticMeshes(root: THREE.Group, kit: MeshKit) {
  const parents: THREE.Object3D[] = []
  root.traverse(part => { if (part instanceof THREE.Group) parents.push(part) })
  const point = new THREE.Vector3(); const normal = new THREE.Vector3(); const normalMatrix = new THREE.Matrix3()
  for (const parent of parents) {
    const surfaces = new Map<Surface, THREE.Mesh<THREE.BufferGeometry, Surface>[]>()
    for (const child of parent.children) if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
      const siblings = surfaces.get(child.material) ?? []
      siblings.push(child); surfaces.set(child.material, siblings)
    }
    for (const [surface, siblings] of surfaces) {
      if (siblings.length < 2) continue
      const vertices = siblings.reduce((sum, part) => sum + (part.geometry.index?.count ?? part.geometry.getAttribute('position').count), 0)
      const positions = new Float32Array(vertices * 3); const normals = new Float32Array(vertices * 3)
      let offset = 0
      // 只烘焙当前关节内固定部件的局部变换；肩肘、髋膝、衣摆和持物关节仍各自活动。
      for (const part of siblings) {
        part.updateMatrix(); normalMatrix.getNormalMatrix(part.matrix)
        const position = part.geometry.getAttribute('position'); const sourceNormal = part.geometry.getAttribute('normal'); const indices = part.geometry.index
        for (let vertex = 0; vertex < (indices?.count ?? position.count); vertex++) {
          const index = indices ? indices.getX(vertex) : vertex
          point.fromBufferAttribute(position, index).applyMatrix4(part.matrix)
          normal.fromBufferAttribute(sourceNormal, index).applyNormalMatrix(normalMatrix)
          point.toArray(positions, offset); normal.toArray(normals, offset); offset += 3
        }
        parent.remove(part)
      }
      const geometry = kit.own(new THREE.BufferGeometry())
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3)); geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3))
      geometry.computeBoundingBox(); geometry.computeBoundingSphere()
      kit.mesh(parent, geometry, surface).name = `${parent.name}Surface`
    }
  }
  const usedGeometries = new Set<THREE.BufferGeometry>(); const usedMaterials = new Set<THREE.Material>()
  root.traverse(part => { if (part instanceof THREE.Mesh) { usedGeometries.add(part.geometry); usedMaterials.add(part.material) } })
  for (const geometry of kit.geometries) if (!usedGeometries.has(geometry)) { geometry.dispose(); kit.geometries.delete(geometry) }
  for (const [key, material] of kit.materials) if (!usedMaterials.has(material)) { material.dispose(); kit.materials.delete(key) }
}

function joint(parent: THREE.Object3D, name: string, position: Point) {
  const part = new THREE.Group(); part.name = name; part.position.set(...position); parent.add(part); return part
}

type ClothRing = { y: number; rx: number; rz: number; x?: number; z?: number }

function clothShell(kit: MeshKit, parent: THREE.Object3D, rings: ClothRing[], surface: Surface, position: Point = [0, 0, 0]) {
  const segments = 16; const positions: number[] = []; const indices: number[] = []
  for (const ring of rings) for (let index = 0; index < segments; index++) {
    const angle = index / segments * Math.PI * 2
    positions.push((ring.x ?? 0) + Math.cos(angle) * ring.rx, ring.y, (ring.z ?? 0) + Math.sin(angle) * ring.rz)
  }
  for (let row = 0; row < rings.length - 1; row++) for (let index = 0; index < segments; index++) {
    const next = (index + 1) % segments; const a = row * segments + index; const b = (row + 1) * segments + index
    const c = row * segments + next; const d = (row + 1) * segments + next
    indices.push(a, c, b, b, c, d)
  }
  const geometry = kit.own(new THREE.BufferGeometry())
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); geometry.setIndex(indices); geometry.computeVertexNormals()
  return kit.mesh(parent, geometry, surface, position)
}

function curvedStitch(kit: MeshKit, parent: THREE.Object3D, points: Point[], radius: number, surface: Surface) {
  const curve = new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point)))
  return kit.mesh(parent, kit.own(new THREE.TubeGeometry(curve, 9, radius, 4, false)), surface)
}

function ellipseTrim(kit: MeshKit, parent: THREE.Object3D, position: Point, rx: number, rz: number, thickness: number, surface: Surface) {
  const ring = kit.mesh(parent, kit.own(new THREE.TorusGeometry(1, thickness, 4, 20)), surface, position, [rx, rz, 1])
  ring.rotation.x = Math.PI / 2
  return ring
}

function createLeg(kit: MeshKit, pelvis: THREE.Group, side: number, profile: Profile): Limb {
  const prefix = side < 0 ? 'left' : 'right'
  const upper = joint(pelvis, `${prefix}Thigh`, [side * (profile.broad ? .19 : .155), 0, 0])
  const cloth = kit.material(profile.lining); const boot = kit.material('#3d4940')
  clothShell(kit, upper, [
    { y: .01, rx: .103, rz: .105 }, { y: -.10, rx: .119, rz: .12 },
    { y: -.28, rx: .112, rz: .11 }, { y: -.43, rx: .094, rz: .092 }, { y: -.49, rx: .088, rz: .087 },
  ], cloth)
  const lower = joint(upper, `${prefix}LowerLeg`, [0, -.49, 0])
  clothShell(kit, lower, [
    { y: .015, rx: .089, rz: .088 }, { y: -.09, rx: .087, rz: .091 },
    { y: -.23, rx: .075, rz: .081 }, { y: -.32, rx: .071, rz: .076 },
  ], cloth)
  clothShell(kit, lower, [
    { y: -.205, rx: .079, rz: .088 }, { y: -.24, rx: .083, rz: .091 },
    { y: -.39, rx: .085, rz: .099 }, { y: -.47, rx: .077, rz: .09 },
  ], boot)
  ellipseTrim(kit, lower, [0, -.235, 0], .084, .092, .014, kit.material(profile.trim))
  const end = joint(lower, `${prefix}Foot`, [0, -.47, 0])
  kit.oval(end, [.095, .068, .178], [0, -.074, .065], boot)
  kit.oval(end, [.096, .018, .185], [0, -.162, .07], kit.material('#303a33'))
  curvedStitch(kit, end, [[-.073, -.055, .19], [0, -.047, .228], [.073, -.055, .19]], .005, kit.material(profile.trim))
  return { upper, lower, end }
}

function createArm(kit: MeshKit, torso: THREE.Group, side: number, profile: Profile): Limb {
  const prefix = side < 0 ? 'left' : 'right'
  const armored = profile.garment === 'armor'
  const upper = joint(torso, `${prefix}UpperArm`, [side * (profile.broad ? .42 : profile.female ? .30 : .35), .70, 0])
  kit.oval(upper, [armored ? .17 : .13, .14, .145], [0, -.035, 0], kit.material(armored ? profile.metal : profile.cloth, armored))
  clothShell(kit, upper, [
    { y: .015, rx: .11, rz: .12 }, { y: -.075, rx: armored ? .13 : .145, rz: .13 },
    { y: -.20, rx: .122, rz: .118 }, { y: -.34, rx: .105, rz: .105 },
  ], kit.material(profile.cloth))
  const lower = joint(upper, `${prefix}Forearm`, [0, -.35, 0])
  const flowing = profile.garment === 'dress' || profile.garment === 'robe'
  clothShell(kit, lower, [
    { y: .015, rx: .115, rz: .12 }, { y: -.07, rx: flowing ? .145 : .11, rz: flowing ? .135 : .10 },
    { y: -.21, rx: flowing ? .176 : .105, rz: flowing ? .16 : .098 },
    { y: -.32, rx: flowing ? .184 : .10, rz: flowing ? .164 : .094 }, { y: -.36, rx: flowing ? .168 : .095, rz: flowing ? .15 : .09 },
  ], kit.material(profile.cloth))
  ellipseTrim(kit, lower, [0, -.345, 0], flowing ? .17 : .096, flowing ? .15 : .09, .012, kit.material(profile.trim))
  if (armored) {
    kit.oval(lower, [.105, .17, .036], [0, -.18, .093], kit.material(profile.metal, true))
    curvedStitch(kit, lower, [[-.07, -.07, .116], [0, -.11, .132], [.07, -.07, .116]], .006, kit.material(profile.trim, true))
  }
  const end = joint(lower, `${prefix}Hand`, [0, -.385, 0])
  kit.oval(end, [.075, .105, .065], [0, -.005, 0], kit.material(profile.skin ?? '#c9a17d'))
  return { upper, lower, end }
}

function createGarment(kit: MeshKit, pelvis: THREE.Group, torso: THREE.Group, profile: Profile) {
  const cloth = kit.material(profile.cloth); const lining = kit.material(profile.lining); const trim = kit.material(profile.trim)
  const armored = profile.garment === 'armor'; const width = profile.broad ? .36 : profile.female ? .25 : .29
  clothShell(kit, torso, [
    { y: .08, rx: width * .86, rz: width * .47 }, { y: .23, rx: width * .84, rz: width * .47 },
    { y: .38, rx: width * .94, rz: width * .51 }, { y: .55, rx: width * 1.06, rz: width * .55 },
    { y: .70, rx: width * .91, rz: width * .46 },
  ], cloth)
  clothShell(kit, pelvis, [
    { y: .17, rx: width * .82, rz: width * .48 }, { y: .04, rx: width * .85, rz: width * .49 },
    { y: -.18, rx: width * .98, rz: width * .57 }, { y: -.50, rx: width * 1.10, rz: width * .66 },
    { y: -.88, rx: width * 1.22, rz: width * .72 },
  ], lining)
  curvedStitch(kit, torso, [[.035, .74, .17], [.12, .63, .205], [.085, .47, .22], [-.04, .32, .20], [-.035, .19, .17]], .011, trim)
  ellipseTrim(kit, pelvis, [0, -.10, 0], width * .92, width * .53, .008, trim)
  const panels: ClothJoint[] = []
  const hem = profile.garment === 'short' ? .48 : armored ? .72 : profile.female ? 1 : .93
  for (const back of [false, true]) for (const side of [-1, 1]) {
    const part = joint(pelvis, `${back ? 'back' : 'front'}Robe${side < 0 ? 'Left' : 'Right'}`, [side * width * .50, .04, back ? -.13 : .14])
    const panelWidth = profile.garment === 'dress' ? .40 : armored ? .31 : .37
    const shape = new THREE.Shape()
    shape.moveTo(-.105, 0); shape.lineTo(.105, 0)
    shape.quadraticCurveTo(.14, -.08, .145, -.18); shape.quadraticCurveTo(.18, -hem * .74, panelWidth / 2, -hem)
    shape.lineTo(-panelWidth / 2, -hem); shape.quadraticCurveTo(-.18, -hem * .74, -.145, -.18); shape.quadraticCurveTo(-.14, -.08, -.105, 0)
    const geometry = kit.own(new THREE.ExtrudeGeometry(shape, { depth: .055, bevelEnabled: true, bevelSegments: 1, bevelThickness: .008, bevelSize: .006 }))
    geometry.translate(0, 0, -.0275)
    const body = kit.mesh(part, geometry, back ? lining : cloth)
    body.rotation.y = side * (back ? -.25 : .16)
    if (!back) curvedStitch(kit, part, [[side * .075, -.10, .04], [side * .10, -hem * .30, .04], [side * .14, -hem * .66, .04], [side * panelWidth * .39, -hem + .035, .04]], .006, trim)
    panels.push({ joint: part, side, back })
  }
  if (armored) {
    const metal = kit.material(profile.metal, true)
    clothShell(kit, torso, [
      { y: .17, rx: width * .88, rz: width * .48 }, { y: .28, rx: width * .91, rz: width * .50 },
      { y: .43, rx: width * 1.00, rz: width * .54 }, { y: .57, rx: width * 1.08, rz: width * .56 },
      { y: .66, rx: width * .90, rz: width * .46 },
    ], metal, [0, 0, .006])
    for (const [y, scale] of [[.27, .91], [.42, 1], [.56, 1.07]]) ellipseTrim(kit, torso, [0, y, .006], width * scale, width * .51, .008, kit.material(profile.trim, true))
    kit.oval(torso, [.055, .10, .035], [0, .62, .208], trim)
  }
  let cape: THREE.Group | undefined
  if (profile.cape) {
    cape = joint(torso, 'cape', [0, .70, -.19])
    kit.solid(cape, [[-.27, 0], [.27, 0], [.42, -1.45], [-.42, -1.45]], .065, [0, 0, 0], kit.material(profile.cape))
    for (const x of [-.22, 0, .22]) kit.box(cape, [.025, 1.25, .028], [x, -.75, -.043], lining)
  }
  return { panels, cape }
}

function createHead(kit: MeshKit, torso: THREE.Group, profile: Profile, templateId: string) {
  const head = joint(torso, 'head', [0, .89, 0]); const hair = kit.material(profile.hair ?? '#303d37')
  const trim = kit.material(profile.trim); const skin = kit.material(profile.skin ?? '#c9a17d')
  const ink = kit.material('#2d3b35')
  kit.pole(head, .075, .14, [0, -.035, 0], skin)
  // 额头、颊面和下颌分层，保留成人比例的面部转折而不是一颗均匀球体。
  kit.oval(head, [.171, .198, .145], [0, .17, 0], skin)
  kit.oval(head, [.145, .122, .13], [0, .055, .035], skin)
  kit.oval(head, [.088, .10, .112], [-.082, .145, .053], skin)
  kit.oval(head, [.088, .10, .112], [.082, .145, .053], skin)
  kit.oval(head, [.18, .17, .16], [0, .285, -.025], hair)
  kit.solid(head, [[-.13, 0], [.13, 0], [.11, -.055], [.07, -.10], [0, -.075], [-.07, -.10], [-.11, -.055]], .07, [0, .30, .10], hair)
  for (const side of [-1, 1]) {
    kit.between(head, [side * .095, .224, .164], [side * .035, .234, .167], .008, ink)
    kit.oval(head, [.023, .008, .006], [side * .062, .202, .166], ink)
  }
  const nose = kit.taper(head, .028, .019, .09, [0, .15, .15], skin, .86)
  nose.rotation.z = .02
  nose.position.z = .17
  kit.between(head, [-.026, .102, .152], [.026, .102, .152], .005, ink)
  if (profile.female || profile.hat === 'loose') for (const side of [-1, 1]) {
    const lock = kit.taper(head, .060, .036, .34, [side * .15, 0, -.072], hair, .88)
    lock.rotation.z = side * .10
  }
  if (profile.hat === 'crown') {
    const crown = kit.taper(head, .13, .17, .19, [0, .445, -.01], kit.material(profile.lining), .78)
    crown.rotation.y = .08
    kit.box(head, [.20, .035, .16], [0, .356, -.015], trim)
    kit.taper(head, .025, .045, .12, [0, .55, .015], trim, .80)
  } else if (profile.hat === 'cap' || profile.hat === 'wrap') {
    kit.taper(head, .125, .185, .13, [0, .395, -.035], kit.material(profile.hat === 'wrap' ? profile.cloth : profile.lining), .82)
    kit.oval(head, [.035, .065, .025], [0, .41, .12], trim)
  } else if (profile.hat === 'helmet') {
    const metal = kit.material(profile.metal, true)
    kit.oval(head, [.19, .17, .17], [0, .355, -.02], metal)
    kit.box(head, [.28, .04, .065], [0, .35, .13], trim)
    for (const side of [-1, 1]) {
      const guard = kit.taper(head, .055, .08, .17, [side * .177, .22, -.03], metal, .80)
      guard.rotation.z = side * .08
    }
    kit.taper(head, .035, .055, .14, [0, .49, -.04], kit.material(profile.cape ?? profile.lining), .90)
  } else if (profile.hat === 'doubleBun') {
    for (const side of [-1, 1]) {
      kit.oval(head, [.105, .11, .10], [side * .16, .40, -.025], hair)
      kit.taper(head, .027, .045, .13, [side * .16, .38, .035], kit.material(profile.lining), .80)
    }
  } else {
    kit.oval(head, [.105, .11, .09], [0, .425, -.08], hair)
    kit.between(head, [-.19, .425, -.04], [.19, .425, -.04], .016, trim)
  }
  const beard = profile.beard ?? 'none'
  if (beard !== 'none') {
    const surface = kit.material(beard === 'white' ? '#d8d6bf' : beard === 'short' ? profile.hair ?? '#475046' : '#303c35')
    const length = beard === 'long' ? .35 : beard === 'wild' ? .26 : beard === 'white' ? .25 : .12
    kit.taper(head, beard === 'wild' ? .14 : .095, .018, length, [0, .025 - length / 2, .13], surface, .6)
    for (const side of [-1, 1]) kit.oval(head, [.07, .022, .027], [side * .057, .095, .16], surface)
  }
  if (templateId === 'yangjian') kit.oval(head, [.016, .042, .014], [0, .28, .158], trim)
  if (templateId === 'change') {
    const moon = kit.mesh(head, kit.own(new THREE.TorusGeometry(.065, .016, 5, 12, Math.PI * 1.45)), trim, [.08, .46, .03]); moon.rotation.z = -.55
  }
  if (templateId === 'baisuzhen') kit.oval(head, [.075, .025, .026], [.12, .43, .055], kit.material(profile.lining)).rotation.z = .6
  return head
}

function addBlade(kit: MeshKit, parent: THREE.Group, profile: Profile, shape: Prop) {
  const steel = kit.material(profile.metal, true); const edge = kit.material('#d8ded0', true)
  const gold = kit.material(profile.trim, true); const wood = kit.material('#756348')
  if (shape === 'sword') {
    kit.taper(parent, .026, .034, .24, [0, -.02, 0], wood)
    kit.between(parent, [-.14, .105, 0], [.14, .105, 0], .018, gold)
    kit.taper(parent, .034, .046, .055, [0, .105, 0], gold, .72)
    kit.solid(parent, [[-.048, .13], [.048, .13], [.032, .79], [.006, 1.02], [-.032, .79]], .045, [0, 0, 0], steel)
    kit.between(parent, [0, .18, .029], [0, .89, .029], .008, edge)
    kit.oval(parent, [.045, .055, .045], [0, -.15, 0], gold)
    return
  }
  kit.taper(parent, .022, .036, 1.86, [0, .15, 0], wood)
  const collar = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.052, .012, 5, 12)), gold, [0, .96, 0]); collar.rotation.x = Math.PI / 2
  if (shape === 'guandao') {
    kit.solid(parent, [[-.035, .95], [.085, 1.00], [.24, 1.15], [.30, 1.35], [.24, 1.57], [.11, 1.69], [.12, 1.37], [-.01, 1.20], [-.055, 1.08]], .055, [0, 0, 0], steel)
    kit.taper(parent, .048, .064, .12, [.02, 1.03, 0], gold, .72)
    kit.between(parent, [.06, 1.17, .029], [.21, 1.48, .029], .007, edge)
  } else if (shape === 'serpent') {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-.02, .98, 0), new THREE.Vector3(.08, 1.10, 0), new THREE.Vector3(-.06, 1.25, 0),
      new THREE.Vector3(.07, 1.37, 0), new THREE.Vector3(.01, 1.52, 0),
    ])
    kit.mesh(parent, kit.own(new THREE.TubeGeometry(curve, 12, .037, 5, false)), steel)
    kit.solid(parent, [[-.03, 1.45], [.02, 1.62], [.08, 1.54], [.06, 1.45]], .06, [0, 0, 0], steel)
    kit.oval(parent, [.028, .045, .028], [.055, 1.55, .036], gold)
  } else {
    kit.solid(parent, [[-.065, 1.00], [0, 1.47], [.065, 1.00], [0, 1.09]], .055, [0, 0, 0], steel)
    if (shape === 'trident') for (const side of [-1, 1]) {
      kit.solid(parent, [[side * .045, 1.04], [side * .16, 1.18], [side * .14, 1.40], [side * .23, 1.20], [side * .19, 1.03]], .04, [0, 0, 0], steel)
      kit.between(parent, [side * .065, 1.08, .025], [side * .18, 1.31, .025], .008, edge)
    }
  }
}

function addHandProp(kit: MeshKit, parent: THREE.Group, profile: Profile) {
  const trim = kit.material(profile.trim, true); const ivory = kit.material('#e7e2cf'); const wood = kit.material('#806847')
  if (['sword', 'spear', 'guandao', 'serpent', 'trident'].includes(profile.prop)) { addBlade(kit, parent, profile, profile.prop); return }
  if (profile.prop === 'fan') {
    kit.taper(parent, .020, .030, .30, [0, .05, 0], wood)
    for (let index = 0; index < 7; index++) {
      const angle = (index - 3) * .16
      const feather = kit.solid(parent, [[-.02, 0], [.045, .035], [.065, .19], [.015, .265], [-.045, .18]], .028,
        [Math.sin(angle) * .19, .17 + Math.cos(angle) * .13, 0], ivory)
      feather.rotation.z = -angle
      kit.between(parent, [0, .07, .027], [Math.sin(angle) * .27, .22 + Math.cos(angle) * .28, .027], .005, trim)
    }
    kit.oval(parent, [.045, .045, .045], [0, .07, .032], trim)
  } else if (profile.prop === 'moon') {
    const crescent = kit.solid(parent, [
      [.02, .34], [.15, .29], [.24, .16], [.25, -.01], [.18, -.17], [.05, -.27], [-.09, -.26],
      [-.18, -.18], [-.08, -.19], [.02, -.13], [.09, -.04], [.11, .07], [.08, .18], [.01, .27],
    ], .042, [0, .17, 0], ivory)
    crescent.rotation.z = -.12
    const rim = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.185, .012, 5, 16, Math.PI * 1.55)), trim, [0, .17, .028]); rim.rotation.z = -.12
    kit.taper(parent, .018, .028, .28, [0, -.02, 0], wood)
    kit.oval(parent, [.038, .038, .038], [0, -.17, 0], trim)
  } else if (profile.prop === 'parasol') {
    kit.taper(parent, .012, .019, 1.37, [0, .43, 0], wood)
    kit.taper(parent, .13, .018, .73, [0, .72, 0], ivory)
    const rim = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.125, .010, 5, 14)), kit.material(profile.lining), [0, .36, .01]); rim.rotation.x = Math.PI / 2
    for (const [x, z] of [[-.10, .01], [.10, .01], [0, -.10]] as const) kit.between(parent, [0, 1.08, .015], [x, .37, z], .007, trim)
    kit.taper(parent, .025, .035, .14, [0, -.26, 0], wood)
  } else if (profile.prop === 'bow') {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, -.50, 0), new THREE.Vector3(.17, -.25, 0), new THREE.Vector3(.23, .06, 0), new THREE.Vector3(.17, .42, 0), new THREE.Vector3(0, .73, 0)])
    kit.mesh(parent, kit.own(new THREE.TubeGeometry(curve, 12, .028, 5, false)), wood)
    kit.between(parent, [0, -.50, 0], [0, .73, 0], .006, ivory)
    kit.taper(parent, .052, .060, .16, [.22, .06, 0], trim, .85)
    for (const y of [.01, .07, .13]) {
      const wrap = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.056, .006, 5, 10)), ivory, [.22, y, 0]); wrap.rotation.x = Math.PI / 2
    }
    kit.oval(parent, [.033, .033, .033], [0, -.51, 0], trim); kit.oval(parent, [.033, .033, .033], [0, .74, 0], trim)
  } else if (profile.prop === 'scroll') {
    kit.solid(parent, [[-.13, 0], [.13, 0], [.115, .23], [-.115, .23]], .075, [0, .0, 0], ivory)
    for (const side of [-1, 1]) {
      const roll = kit.pole(parent, .042, .27, [side * .14, .11, 0], wood); roll.rotation.z = Math.PI / 2
      const cap = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.044, .007, 5, 10)), trim, [side * .14, .11, .04]); cap.rotation.z = Math.PI / 2
    }
    kit.taper(parent, .012, .018, .18, [0, .11, .043], trim, .7)
  } else if (profile.prop === 'armillary') {
    for (const rotation of [[0, 0, 0], [Math.PI / 2, 0, 0], [.5, .7, .18]]) {
      const ring = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.15, .012, 5, 16)), trim, [0, .19, 0]); ring.rotation.set(rotation[0]!, rotation[1]!, rotation[2]!)
    }
    kit.taper(parent, .020, .034, .20, [0, .025, 0], wood)
    kit.between(parent, [-.11, -.06, 0], [.11, -.06, 0], .015, wood)
    kit.oval(parent, [.037, .037, .037], [0, .19, 0], trim)
  } else if (profile.prop === 'herbs') {
    for (const side of [-1, 0, 1]) {
      kit.between(parent, [0, -.02, 0], [side * .06, .27, 0], .01, wood)
      const leaf = kit.solid(parent, [[0, 0], [.055, .06], [.015, .16], [-.045, .07]], .024, [side * .065, .19, 0], kit.material('#637c51'))
      leaf.rotation.z = side * -.5
    }
    kit.taper(parent, .07, .10, .16, [0, .04, 0], ivory, .85)
    kit.between(parent, [-.075, .09, .045], [.075, .09, .045], .008, trim)
  } else {
    const stones = ['#7f9387', '#a6a994', '#6c827c']
    for (const side of [-1, 0, 1]) {
      const stone = kit.solid(parent, [[-.045, 0], [.035, -.025], [.055, .035], [.005, .075], [-.05, .05]], .07,
        [side * .06, .07 + (side === 0 ? .04 : 0), 0], kit.material(stones[side + 1]!))
      stone.rotation.z = side * .16
    }
    kit.between(parent, [-.10, .02, .04], [.10, .02, .04], .007, trim)
  }
}

function addIdentityDetails(kit: MeshKit, torso: THREE.Group, pelvis: THREE.Group, profile: Profile, templateId: string) {
  const wood = kit.material('#826c4a'); const trim = kit.material(profile.trim)
  if (templateId === 'libai' || templateId === 'zhouyu') {
    const scabbard = joint(torso, 'swordScabbard', [-.23, .25, -.22]); scabbard.rotation.z = -.46
    kit.taper(scabbard, .052, .073, 1.10, [0, 0, 0], kit.material(profile.lining), .84)
    for (const y of [-.52, .52]) {
      const cap = kit.mesh(scabbard, kit.own(new THREE.TorusGeometry(.065, .010, 5, 10)), trim, [0, y, 0]); cap.rotation.x = Math.PI / 2
    }
    kit.oval(scabbard, [.045, .055, .045], [0, -.59, 0], wood)
  }
  if (templateId === 'libai') {
    kit.oval(pelvis, [.09, .11, .075], [-.31, -.15, .03], wood)
    kit.taper(pelvis, .045, .065, .11, [-.31, -.005, .03], wood)
    const ring = kit.mesh(pelvis, kit.own(new THREE.TorusGeometry(.055, .008, 5, 10)), trim, [-.31, .05, .03]); ring.rotation.x = Math.PI / 2
  }
  if (templateId === 'huatuo') {
    kit.solid(pelvis, [[-.15, 0], [.15, 0], [.12, .28], [-.12, .28]], .18, [-.34, -.33, -.02], wood)
    kit.taper(pelvis, .13, .15, .035, [-.34, -.19, -.02], trim, .75)
    kit.between(torso, [-.20, .70, -.20], [.29, .10, .20], .022, wood)
  }
  if (templateId === 'houyi') {
    const quiver = joint(torso, 'quiver', [-.25, .20, -.24]); quiver.rotation.z = -.20
    kit.taper(quiver, .07, .10, .58, [0, 0, 0], wood)
    const rim = kit.mesh(quiver, kit.own(new THREE.TorusGeometry(.085, .010, 5, 10)), trim, [0, .28, 0]); rim.rotation.x = Math.PI / 2
    for (const side of [-1, 0, 1]) {
      kit.pole(quiver, .009, .67, [side * .035, .21, 0], trim)
      kit.taper(quiver, .012, .019, .11, [side * .035, .52, 0], kit.material(profile.lining), .7)
    }
  }
  if (templateId === 'jingwei') {
    for (const side of [-1, 1]) for (let feather = 0; feather < 3; feather++) {
      const plume = kit.solid(torso, [[0, 0], [.06, .05], [.04, .20], [-.035, .14], [-.055, .04]], .04,
        [side * (.25 + feather * .025), .62 - feather * .065, -.05], kit.material(feather % 2 ? profile.lining : profile.trim))
      plume.rotation.z = side * .55
    }
    kit.solid(pelvis, [[-.12, 0], [.12, 0], [.10, .18], [-.08, .21], [-.13, .12]], .13, [-.30, -.28, .03], wood)
  }
  if (templateId === 'nezha') {
    kit.mesh(pelvis, kit.own(new THREE.TorusGeometry(.12, .023, 5, 16)), trim, [-.28, -.18, .11])
    for (const side of [-1, 1]) {
      const ribbon = kit.solid(pelvis, [[-.035, 0], [.035, 0], [.055, .42], [-.02, .45]], .035,
        [side * .25, -.20, -.08], kit.material(profile.lining))
      ribbon.rotation.z = side * .22
    }
  }
  if (templateId === 'zhangheng') {
    const sash = kit.solid(pelvis, [[-.025, 0], [.025, 0], [.045, .35], [-.035, .35]], .045, [-.29, -.08, .07], trim)
    sash.rotation.z = -.25
  }
}

export function createCultivatorModel(identity: { templateId: string; enemy?: boolean; boss?: boolean }) {
  const profile = profiles[identity.templateId] ?? (identity.enemy ? identity.boss ? sectMaster : guard : wanderer)
  const kit = createMeshKit(); const group = new THREE.Group(); group.name = `cultivator:${identity.templateId}`
  const pelvis = joint(group, 'pelvis', [0, 1.14, 0]); const torso = joint(pelvis, 'torso', [0, .10, 0])
  const leftLeg = createLeg(kit, pelvis, -1, profile); const rightLeg = createLeg(kit, pelvis, 1, profile)
  const cloth = createGarment(kit, pelvis, torso, profile)
  const leftArm = createArm(kit, torso, -1, profile); const rightArm = createArm(kit, torso, 1, profile)
  const head = createHead(kit, torso, profile, identity.templateId)
  const weapon = joint(rightArm.end, 'weapon', [0, -.015, .025]); addHandProp(kit, weapon, profile)
  addIdentityDetails(kit, torso, pelvis, profile, identity.templateId)
  mergeStaticMeshes(group, kit)
  const sword = profile.prop === 'sword'; const polearm = ['spear', 'guandao', 'trident', 'serpent'].includes(profile.prop)
  let disposed = false

  function pose(input: { time: number; walking?: boolean; phase?: 'idle' | 'windup' | 'contact' | 'recover'; hit?: boolean; fallen?: boolean; melee?: boolean }) {
    if (disposed) return
    const time = input.time; const phase = input.phase ?? 'idle'
    const walking = !!input.walking && phase === 'idle' && !input.fallen
    const step = walking ? Math.sin(time * 6.5) : 0
    const windup = phase === 'windup' ? 1 : 0; const contact = phase === 'contact' ? 1 : 0; const recover = phase === 'recover' ? 1 : 0
    const melee = input.melee !== false; const action = windup + contact + recover * .35
    pelvis.position.set(0, input.fallen ? .30 : 1.14, input.hit && !input.fallen ? -.06 : 0)
    pelvis.rotation.set(input.fallen ? .14 : 0, walking ? step * .055 : 0, input.fallen ? -Math.PI / 2 : 0)
    torso.position.y = .10 + (walking || action || input.fallen ? 0 : Math.sin(time * 1.8) * .008)
    torso.rotation.set(input.hit ? .20 : walking ? -.035 : contact ? -.09 : 0, melee ? -windup * .31 + contact * .38 + recover * .12 : 0, input.hit ? -.05 : 0)
    head.rotation.set(input.fallen ? .18 : input.hit ? -.13 : 0, melee ? windup * .13 - contact * .13 : 0, 0)
    for (const [leg, direction] of [[leftLeg, 1], [rightLeg, -1]] as const) {
      const stride = step * direction
      const upperAngle = stride * .37; const lowerAngle = Math.max(0, -stride) * .55
      leg.upper.rotation.set(upperAngle, 0, 0); leg.lower.rotation.set(lowerAngle, 0, 0); leg.end.rotation.set(-upperAngle - lowerAngle, 0, 0)
      // 站立脚保留脚底原点；摆腿才抬脚，不用整个人物上下漂移代替步态。
      leg.upper.position.y = .49 * Math.cos(upperAngle) + .47 * Math.cos(upperAngle + lowerAngle) - .96 + Math.max(0, stride) * .10
    }
    leftArm.upper.rotation.set(step * -.22 - .10, 0, .10); rightArm.upper.rotation.set(step * .22 - .14, 0, -.10)
    leftArm.lower.rotation.set(-.20, 0, 0); rightArm.lower.rotation.set(polearm ? -.12 : -.38, 0, 0)
    weapon.rotation.set(sword ? Math.PI : 0, 0, polearm ? -.12 : -.08)
    if (action && melee) {
      rightArm.upper.rotation.set(-windup * 2.08 - contact * 1.06 - recover * .50, -windup * .25 + contact * .20, -.10 - windup * .30)
      rightArm.lower.rotation.x = -.24 - windup * .45
      leftArm.upper.rotation.set(-.20 - windup * .35 - contact * .75, 0, .20)
      leftArm.lower.rotation.x = -.55
      weapon.rotation.x = sword ? Math.PI : polearm ? windup * .70 + contact * Math.PI + recover * .55 : contact * -.45
    } else if (action) {
      leftArm.upper.rotation.set(-.45 - windup * .35 - contact * .86 - recover * .22, -.20, .18)
      leftArm.lower.rotation.x = -.40 + contact * .20
      rightArm.upper.rotation.set(-.30 - windup * .25 - contact * .25, .10, -.14)
      rightArm.lower.rotation.x = -.70
      weapon.rotation.x = sword ? Math.PI : -.12
    }
    if (input.fallen) { leftArm.upper.rotation.z = .48; rightArm.upper.rotation.z = -.35; head.rotation.z = -.14 }
    for (const panel of cloth.panels) panel.joint.rotation.x = walking ? step * panel.side * (panel.back ? -.08 : .10) : contact ? -.06 : 0
    if (cloth.cape) cloth.cape.rotation.x = walking ? -.07 + Math.sin(time * 6.5 - .6) * .045 : contact ? -.18 : -.035
    for (const surface of kit.materials.values()) { surface.emissive.set(input.hit ? '#9e583b' : '#000000'); surface.emissiveIntensity = input.hit ? .23 : 0 }
  }
  pose({ time: 0 })
  return { group, pose, dispose() {
    if (disposed) return
    disposed = true
    for (const geometry of kit.geometries) geometry.dispose()
    for (const material of kit.materials.values()) material.dispose()
    kit.geometries.clear(); kit.materials.clear(); group.clear()
  } }
}
