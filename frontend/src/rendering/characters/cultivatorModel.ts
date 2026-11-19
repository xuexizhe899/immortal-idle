import * as THREE from 'three'

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
  const cube = own(new THREE.BoxGeometry(1, 1, 1))
  const sphere = own(new THREE.SphereGeometry(1, 10, 7))
  const cylinder = own(new THREE.CylinderGeometry(1, 1, 1, 8))
  function material(color: string, metal = false) {
    const key = `${color}:${metal}`
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({ color, roughness: metal ? .66 : .93, metalness: metal ? .35 : 0, flatShading: true }))
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
    return mesh(parent, own(new THREE.CylinderGeometry(top, bottom, height, 8)), surface, position, [1, 1, depth])
  }
  function solid(parent: THREE.Object3D, points: [number, number][], depth: number, position: Point, surface: Surface) {
    const outline = new THREE.Shape()
    points.forEach(([x, y], index) => index ? outline.lineTo(x, y) : outline.moveTo(x, y)); outline.closePath()
    const geometry = own(new THREE.ExtrudeGeometry(outline, { depth, bevelEnabled: false }))
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

function createLeg(kit: MeshKit, pelvis: THREE.Group, side: number, profile: Profile): Limb {
  const prefix = side < 0 ? 'left' : 'right'
  const upper = joint(pelvis, `${prefix}Thigh`, [side * (profile.broad ? .19 : .155), 0, 0])
  const cloth = kit.material(profile.lining); const boot = kit.material('#3d4940')
  kit.taper(upper, .115, .092, .49, [0, -.245, 0], cloth, .9)
  const lower = joint(upper, `${prefix}LowerLeg`, [0, -.49, 0])
  kit.taper(lower, .092, .068, .47, [0, -.235, 0], cloth, .9)
  kit.taper(lower, .10, .077, .25, [0, -.345, 0], boot, 1)
  const end = joint(lower, `${prefix}Foot`, [0, -.47, 0])
  kit.box(end, [.18, .18, .34], [0, -.09, .065], boot)
  kit.box(end, [.185, .035, .35], [0, -.1625, .07], kit.material('#303a33'))
  kit.box(lower, [.13, .025, .025], [0, -.25, .088], kit.material(profile.trim))
  return { upper, lower, end }
}

function createArm(kit: MeshKit, torso: THREE.Group, side: number, profile: Profile): Limb {
  const prefix = side < 0 ? 'left' : 'right'
  const armored = profile.garment === 'armor'
  const upper = joint(torso, `${prefix}UpperArm`, [side * (profile.broad ? .42 : profile.female ? .30 : .35), .70, 0])
  kit.oval(upper, [armored ? .16 : .12, .15, .14], [0, -.055, 0], kit.material(armored ? profile.metal : profile.cloth, armored))
  kit.taper(upper, .12, armored ? .115 : .15, .35, [0, -.175, 0], kit.material(profile.cloth), 1)
  const lower = joint(upper, `${prefix}Forearm`, [0, -.35, 0])
  const sleeve = profile.garment === 'dress' || profile.garment === 'robe'
  kit.taper(lower, .13, sleeve ? .195 : .095, .34, [0, -.17, 0], kit.material(profile.cloth), sleeve ? .85 : 1)
  kit.taper(lower, sleeve ? .193 : .10, sleeve ? .19 : .10, .055, [0, -.315, 0], kit.material(profile.trim), .86)
  if (armored) kit.box(lower, [.15, .20, .07], [0, -.19, .095], kit.material(profile.metal, true))
  const end = joint(lower, `${prefix}Hand`, [0, -.385, 0])
  kit.oval(end, [.075, .105, .065], [0, -.005, 0], kit.material(profile.skin ?? '#c9a17d'))
  return { upper, lower, end }
}

function createGarment(kit: MeshKit, pelvis: THREE.Group, torso: THREE.Group, profile: Profile) {
  const cloth = kit.material(profile.cloth); const lining = kit.material(profile.lining); const trim = kit.material(profile.trim)
  const armored = profile.garment === 'armor'; const width = profile.broad ? .36 : profile.female ? .25 : .29
  kit.taper(torso, width * 1.08, width * .82, .65, [0, .40, 0], cloth, .68)
  kit.taper(pelvis, width * .85, width * 1.05, .32, [0, .04, 0], lining, .67)
  const collarLeft = kit.box(torso, [.085, .51, .045], [-.10, .48, .19], lining); collarLeft.rotation.z = -.36
  const collarRight = kit.box(torso, [.075, .42, .05], [.095, .48, .20], lining); collarRight.rotation.z = .40
  kit.taper(pelvis, width * .91, width * .91, .105, [0, .12, 0], trim, .75)
  kit.box(pelvis, [.105, .11, .045], [0, .12, width * .75], kit.material(profile.metal, true))
  const panels: ClothJoint[] = []
  const hem = profile.garment === 'short' ? .48 : armored ? .72 : profile.female ? 1 : .93
  for (const back of [false, true]) for (const side of [-1, 1]) {
    const part = joint(pelvis, `${back ? 'back' : 'front'}Robe${side < 0 ? 'Left' : 'Right'}`, [side * width * .50, .04, back ? -.13 : .14])
    const panelWidth = profile.garment === 'dress' ? .40 : armored ? .31 : .37
    const body = kit.solid(part, [[-.12, 0], [.12, 0], [panelWidth / 2, -hem], [-panelWidth / 2, -hem]], .08, [0, 0, 0], back ? lining : cloth)
    body.rotation.y = side * (back ? -.25 : .16)
    kit.box(part, [.027, hem * .9, .025], [side * panelWidth * .25, -hem * .49, .057], trim)
    panels.push({ joint: part, side, back })
  }
  if (armored) {
    const metal = kit.material(profile.metal, true)
    kit.taper(torso, width * 1.10, width * .88, .49, [0, .40, .006], metal, .74)
    for (const y of [.28, .41, .54]) for (const side of [-1, 1]) {
      kit.box(torso, [width * .72, .07, .045], [side * width * .47, y, .22], kit.material(profile.trim, true))
    }
    kit.box(torso, [.10, .17, .055], [0, .59, .23], trim)
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
  kit.pole(head, .075, .14, [0, -.025, 0], skin)
  kit.oval(head, [.172, .215, .16], [0, .18, .005], skin)
  kit.oval(head, [.18, .17, .17], [0, .27, -.027], hair)
  kit.oval(head, [.12, .23, .07], [0, .11, -.135], hair)
  kit.oval(head, [.042, .055, .045], [-.168, .16, 0], skin); kit.oval(head, [.042, .055, .045], [.168, .16, 0], skin)
  kit.box(head, [.040, .055, .055], [0, .175, .161], skin)
  for (const side of [-1, 1]) {
    kit.box(head, [.045, .016, .015], [side * .067, .228, .151], hair)
    kit.box(head, [.034, .012, .016], [side * .067, .206, .157], kit.material('#33473e'))
  }
  if (profile.female || profile.hat === 'loose') for (const side of [-1, 1]) {
    kit.oval(head, [.055, .30, .065], [side * .15, -.03, -.09], hair)
  }
  if (profile.hat === 'crown') {
    kit.taper(head, .12, .16, .21, [0, .44, -.015], kit.material(profile.lining), .74)
    kit.box(head, [.19, .035, .22], [0, .36, -.02], trim)
    kit.box(head, [.033, .18, .023], [0, .44, .10], trim)
  } else if (profile.hat === 'cap' || profile.hat === 'wrap') {
    kit.taper(head, .115, .185, .125, [0, .39, -.025], kit.material(profile.hat === 'wrap' ? profile.cloth : profile.lining), .83)
    kit.box(head, [.045, .08, .025], [0, .395, .12], trim)
  } else if (profile.hat === 'helmet') {
    const metal = kit.material(profile.metal, true)
    kit.oval(head, [.195, .16, .175], [0, .335, -.02], metal)
    kit.box(head, [.28, .04, .065], [0, .35, .13], trim)
    for (const side of [-1, 1]) kit.box(head, [.045, .18, .15], [side * .177, .19, -.03], metal)
    kit.oval(head, [.045, .15, .05], [0, .49, -.04], kit.material(profile.cape ?? profile.lining))
  } else if (profile.hat === 'doubleBun') {
    for (const side of [-1, 1]) {
      kit.oval(head, [.10, .10, .10], [side * .16, .37, -.025], hair)
      kit.box(head, [.05, .035, .14], [side * .16, .37, .015], kit.material(profile.lining))
    }
  } else {
    kit.oval(head, [.105, .105, .09], [0, .415, -.08], hair)
    kit.between(head, [-.19, .42, -.04], [.19, .42, -.04], .016, trim)
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
  const steel = kit.material(profile.metal, true); const gold = kit.material(profile.trim, true); const wood = kit.material('#756348')
  if (shape === 'sword') {
    kit.pole(parent, .028, .21, [0, -.02, 0], wood)
    kit.box(parent, [.25, .045, .065], [0, .105, 0], gold)
    kit.solid(parent, [[-.047, .12], [.047, .12], [.036, .88], [0, 1.02], [-.036, .88]], .045, [0, 0, 0], steel)
    kit.box(parent, [.016, .70, .013], [0, .49, .029], kit.material('#d8ded0', true))
    return
  }
  kit.pole(parent, .032, 1.83, [0, .16, 0], wood)
  kit.pole(parent, .040, .13, [0, .96, 0], gold)
  if (shape === 'guandao') {
    kit.solid(parent, [[-.035, .94], [.10, .99], [.28, 1.18], [.23, 1.46], [.11, 1.62], [.13, 1.30], [-.035, 1.16]], .055, [0, 0, 0], steel)
    kit.box(parent, [.12, .055, .07], [.025, 1.03, 0], gold)
  } else if (shape === 'serpent') {
    kit.solid(parent, [[-.03, .99], [.06, 1.12], [-.04, 1.27], [.05, 1.43], [.01, 1.58], [-.04, 1.40], [-.10, 1.26], [.00, 1.10]], .055, [0, 0, 0], steel)
  } else {
    kit.solid(parent, [[-.07, 1.00], [0, 1.45], [.07, 1.00], [0, 1.08]], .055, [0, 0, 0], steel)
    if (shape === 'trident') for (const side of [-1, 1]) kit.solid(parent, [[side * .055, 1.03], [side * .18, 1.15], [side * .15, 1.37], [side * .23, 1.19], [side * .19, 1.03]], .04, [0, 0, 0], steel)
  }
}

function addHandProp(kit: MeshKit, parent: THREE.Group, profile: Profile) {
  const trim = kit.material(profile.trim, true); const ivory = kit.material('#e7e2cf'); const wood = kit.material('#806847')
  if (['sword', 'spear', 'guandao', 'serpent', 'trident'].includes(profile.prop)) { addBlade(kit, parent, profile, profile.prop); return }
  if (profile.prop === 'fan') {
    kit.pole(parent, .018, .30, [0, .05, 0], wood)
    for (let index = 0; index < 7; index++) {
      const angle = (index - 3) * .16
      kit.oval(parent, [.044, .24, .026], [Math.sin(angle) * .21, .25 + Math.cos(angle) * .13, 0], ivory).rotation.z = -angle
      kit.between(parent, [0, .07, .027], [Math.sin(angle) * .28, .25 + Math.cos(angle) * .29, .027], .005, trim)
    }
  } else if (profile.prop === 'moon') {
    const disk = kit.pole(parent, .17, .045, [0, .17, 0], ivory); disk.rotation.x = Math.PI / 2
    kit.mesh(parent, kit.own(new THREE.TorusGeometry(.138, .013, 5, 16)), trim, [0, .17, .03])
  } else if (profile.prop === 'parasol') {
    kit.pole(parent, .016, 1.37, [0, .43, 0], wood)
    kit.taper(parent, .018, .12, .73, [0, .72, 0], ivory)
    for (const side of [-1, 1]) kit.between(parent, [0, 1.09, .015], [side * .10, .35, .015], .008, kit.material(profile.lining))
  } else if (profile.prop === 'bow') {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, -.50, 0), new THREE.Vector3(.17, -.25, 0), new THREE.Vector3(.23, .06, 0), new THREE.Vector3(.17, .42, 0), new THREE.Vector3(0, .73, 0)])
    kit.mesh(parent, kit.own(new THREE.TubeGeometry(curve, 12, .028, 5, false)), wood)
    kit.between(parent, [0, -.50, 0], [0, .73, 0], .006, ivory)
    kit.box(parent, [.07, .17, .055], [.22, .06, 0], trim)
  } else if (profile.prop === 'scroll') {
    kit.box(parent, [.25, .15, .10], [0, .11, 0], ivory)
    for (const side of [-1, 1]) kit.pole(parent, .035, .20, [side * .14, .11, 0], wood)
  } else if (profile.prop === 'armillary') {
    for (const rotation of [[0, 0, 0], [Math.PI / 2, 0, 0], [.5, .7, 0]]) {
      const ring = kit.mesh(parent, kit.own(new THREE.TorusGeometry(.15, .014, 5, 16)), trim, [0, .19, 0]); ring.rotation.set(rotation[0]!, rotation[1]!, rotation[2]!)
    }
    kit.pole(parent, .03, .18, [0, .025, 0], wood); kit.oval(parent, [.035, .035, .035], [0, .19, 0], trim)
  } else if (profile.prop === 'herbs') {
    for (const side of [-1, 0, 1]) {
      kit.between(parent, [0, -.02, 0], [side * .06, .27, 0], .01, wood)
      kit.oval(parent, [.045, .085, .018], [side * .065, .24, 0], kit.material('#637c51')).rotation.z = side * -.5
    }
    kit.box(parent, [.15, .035, .09], [0, .06, 0], ivory)
  } else {
    for (const side of [-1, 0, 1]) kit.oval(parent, [.05, .045, .045], [side * .06, .07 + (side === 0 ? .04 : 0), 0], kit.material('#919986'))
  }
}

function addIdentityDetails(kit: MeshKit, torso: THREE.Group, pelvis: THREE.Group, profile: Profile, templateId: string) {
  const wood = kit.material('#826c4a'); const trim = kit.material(profile.trim)
  if (templateId === 'libai' || templateId === 'zhouyu') {
    const scabbard = joint(torso, 'swordScabbard', [-.23, .25, -.22]); scabbard.rotation.z = -.46
    kit.box(scabbard, [.085, 1.08, .07], [0, 0, 0], kit.material(profile.lining)); kit.box(scabbard, [.20, .04, .09], [0, .57, 0], trim)
  }
  if (templateId === 'libai') {
    kit.oval(pelvis, [.09, .11, .075], [-.31, -.15, .03], wood); kit.oval(pelvis, [.065, .075, .06], [-.31, -.015, .03], wood)
  }
  if (templateId === 'huatuo') {
    kit.box(pelvis, [.28, .29, .20], [-.34, -.19, -.02], wood)
    kit.box(pelvis, [.30, .055, .21], [-.34, -.055, -.02], trim)
    kit.between(torso, [-.20, .70, -.20], [.29, .10, .20], .022, wood)
  }
  if (templateId === 'houyi') {
    const quiver = joint(torso, 'quiver', [-.25, .20, -.24]); quiver.rotation.z = -.20
    kit.pole(quiver, .09, .58, [0, 0, 0], wood)
    for (const side of [-1, 0, 1]) {
      kit.pole(quiver, .009, .67, [side * .035, .21, 0], trim)
      kit.box(quiver, [.04, .11, .015], [side * .035, .52, 0], kit.material(profile.lining))
    }
  }
  if (templateId === 'jingwei') {
    for (const side of [-1, 1]) for (let feather = 0; feather < 3; feather++) {
      kit.oval(torso, [.08, .20, .04], [side * (.25 + feather * .025), .62 - feather * .065, -.05], kit.material(feather % 2 ? profile.lining : profile.trim)).rotation.z = side * .55
    }
    kit.oval(pelvis, [.13, .16, .08], [-.30, -.19, .03], wood)
  }
  if (templateId === 'nezha') {
    kit.mesh(pelvis, kit.own(new THREE.TorusGeometry(.12, .023, 5, 16)), trim, [-.28, -.18, .11])
    for (const side of [-1, 1]) kit.box(pelvis, [.09, .43, .035], [side * .25, -.20, -.08], kit.material(profile.lining)).rotation.z = side * .22
  }
  if (templateId === 'zhangheng') kit.box(pelvis, [.055, .35, .045], [-.29, -.08, .07], trim).rotation.z = -.25
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
