import * as THREE from 'three'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'
import { CITY_BUILDINGS } from './cityModel'

type Building = (typeof CITY_BUILDINGS)[number]
type Surface = 'jade' | 'stone' | 'wood' | 'roof' | 'grass'
export const CITY_WORLD_SCALE = 1.1

const PALETTES: Record<Surface, readonly string[]> = {
  jade: ['#e2e2ca', '#d2d7bd', '#f2efda', '#bcc7ad'],
  stone: ['#7e9083', '#8e9e8c', '#6b8176', '#acb49d'],
  wood: ['#715441', '#876449', '#a17c55', '#5f4939'],
  roof: ['#365e58', '#416c63', '#294d4a', '#587a68'],
  grass: ['#7e9a72', '#91a87c', '#6c8d68', '#a8b78a'],
}

function pixelTexture(kind: Surface) {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 64
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建场景纹理画布')
  const colors = PALETTES[kind]
  // 固定纹理坐标决定纹样，重进场景不会消耗玩法随机数或改变地形。
  for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) {
    const hash = ((x * 73856093) ^ (y * 19349663)) >>> 0
    const joint = kind === 'roof' ? x % 8 === 0 || y % 8 === 7
      : kind === 'wood' ? x % 12 === 0 : kind === 'jade' ? y % 16 === 0 || (x + (y >> 4) * 8) % 24 === 0 : false
    context.fillStyle = colors[joint ? 3 : hash % 13 === 0 ? 2 : hash % 5 === 0 ? 1 : 0]!
    context.fillRect(x, y, 1, 1)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.magFilter = THREE.NearestFilter
  texture.minFilter = THREE.NearestFilter
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.generateMipmaps = false
  return texture
}

function hipRoofGeometry(width: number, depth: number, height: number) {
  const vertices: number[] = []
  const uvs: number[] = []
  const quad = (a: number[], b: number[], c: number[], d: number[]) => {
    for (const p of [a, b, d, b, c, d]) {
      vertices.push(...p)
      uvs.push(p[0]! / width + 0.5, p[2]! / depth + 0.5)
    }
  }
  // 两段屋面让檐口微翘；山墙端收向屋脊，保留立体屋顶而非平面贴图。
  const bands = [
    { z: depth / 2, x: width / 2, y: 0.13 },
    { z: depth * 0.32, x: width * 0.46, y: height * 0.22 },
    { z: 0, x: width * 0.31, y: height },
  ]
  for (const side of [-1, 1]) for (let i = 0; i < bands.length - 1; i++) {
    const a = bands[i]!, b = bands[i + 1]!
    quad([-a.x, a.y, side * a.z], [a.x, a.y, side * a.z], [b.x, b.y, side * b.z], [-b.x, b.y, side * b.z])
  }
  for (const side of [-1, 1]) {
    const outer = bands[0]!, middle = bands[1]!, top = bands[2]!
    quad([side * outer.x, outer.y, -outer.z], [side * outer.x, outer.y, outer.z], [side * middle.x, middle.y, middle.z], [side * middle.x, middle.y, -middle.z])
    quad([side * middle.x, middle.y, -middle.z], [side * middle.x, middle.y, middle.z], [side * top.x, top.y, 0], [side * top.x, top.y, 0])
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3))
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  geometry.computeVertexNormals()
  return geometry
}

class CityBuilder {
  readonly group = new THREE.Group()
  readonly buildings = new Map<string, THREE.Group>()
  readonly lamps: THREE.Mesh[] = []
  worldGround!: THREE.Mesh<THREE.BufferGeometry, THREE.Material>
  private readonly geometries = new Set<THREE.BufferGeometry>()
  private readonly materials = new Set<THREE.Material>()
  private readonly textures = new Set<THREE.Texture>()
  private readonly cube = this.geometry(new THREE.BoxGeometry(1, 1, 1))
  private readonly surfaces: Record<Surface, THREE.MeshStandardMaterial>
  private readonly dark: THREE.MeshStandardMaterial
  private readonly gold: THREE.MeshStandardMaterial
  private readonly foliage: THREE.MeshStandardMaterial
  private readonly glow: THREE.MeshStandardMaterial

  constructor() {
    const surface = (kind: Surface) => {
      const map = pixelTexture(kind)
      this.textures.add(map)
      return this.material(new THREE.MeshStandardMaterial({ map, roughness: 1, side: THREE.DoubleSide }))
    }
    this.surfaces = { jade: surface('jade'), stone: surface('stone'), wood: surface('wood'), roof: surface('roof'), grass: surface('grass') }
    this.dark = this.material(new THREE.MeshStandardMaterial({ color: '#304b46', roughness: 1 }))
    this.gold = this.material(new THREE.MeshStandardMaterial({ color: '#b89d59', roughness: 0.8 }))
    this.foliage = this.material(new THREE.MeshStandardMaterial({ color: '#607f5c', roughness: 1, flatShading: true }))
    this.glow = this.material(new THREE.MeshStandardMaterial({ color: '#f8d995', emissive: '#ffb84e', emissiveIntensity: 0.3, roughness: 1 }))
  }

  private geometry<T extends THREE.BufferGeometry>(geometry: T): T {
    this.geometries.add(geometry)
    return geometry
  }

  private material<T extends THREE.Material>(material: T): T {
    this.materials.add(material)
    return material
  }

  private mesh(parent: THREE.Object3D, geometry: THREE.BufferGeometry, material: THREE.Material, x: number, y: number, z: number) {
    const mesh = new THREE.Mesh(geometry, material)
    mesh.position.set(x, y, z)
    mesh.castShadow = mesh.receiveShadow = true
    parent.add(mesh)
    return mesh
  }

  private box(parent: THREE.Object3D, width: number, height: number, depth: number, x: number, y: number, z: number, material: THREE.Material) {
    const mesh = this.mesh(parent, this.cube, material, x, y, z)
    mesh.scale.set(width, height, depth)
    return mesh
  }

  private cylinder(parent: THREE.Object3D, top: number, bottom: number, height: number, x: number, y: number, z: number, material: THREE.Material, sides = 8) {
    return this.mesh(parent, this.geometry(new THREE.CylinderGeometry(top, bottom, height, sides)), material, x, y, z)
  }

  private lamp(parent: THREE.Object3D, x: number, y: number, z: number, size = 0.22) {
    const lamp = this.box(parent, size, size * 1.5, size, x, y, z, this.glow)
    lamp.castShadow = false
    lamp.userData.cityLamp = true
    this.lamps.push(lamp)
    return lamp
  }

  private roof(parent: THREE.Object3D, width: number, depth: number, y: number, height: number) {
    this.mesh(parent, this.geometry(hipRoofGeometry(width, depth, height)), this.surfaces.roof, 0, y, 0)
    this.box(parent, width * 0.64, 0.13, 0.15, 0, y + height + 0.03, 0, this.dark)
    for (const side of [-1, 1]) {
      this.box(parent, width + 0.05, 0.1, 0.13, 0, y + 0.1, side * depth / 2, this.dark)
      this.box(parent, 0.14, 0.25, 0.2, side * width * 0.32, y + height + 0.12, 0, this.gold)
    }
  }

  private foundation(parent: THREE.Object3D, width: number, depth: number) {
    this.box(parent, width + 0.5, 0.3, depth + 0.5, 0, 0.15, 0, this.surfaces.stone)
    this.box(parent, width + 0.2, 0.16, depth + 0.2, 0, 0.38, 0, this.surfaces.jade)
    for (let step = 0; step < 3; step++) this.box(parent, width * 0.46, 0.12, 0.42, 0, 0.06 + step * 0.12, depth / 2 + 1.03 - step * 0.35, this.surfaces.jade)
  }

  private pavilion(parent: THREE.Object3D, width: number, depth: number, height: number, floor = 0.45, enclosed = true) {
    if (enclosed) {
      this.box(parent, width * 0.86, height * 0.82, depth * 0.8, 0, floor + height * 0.41, 0, this.surfaces.jade)
      this.box(parent, width * 0.24, height * 0.72, 0.08, 0, floor + height * 0.36, depth * 0.405, this.dark)
      this.box(parent, width * 0.27, 0.12, 0.13, 0, floor + height * 0.74, depth * 0.42, this.gold)
      for (const side of [-1, 1]) {
        this.box(parent, width * 0.17, height * 0.31, 0.08, side * width * 0.29, floor + height * 0.49, depth * 0.41, this.dark)
        this.box(parent, width * 0.19, 0.07, 0.14, side * width * 0.29, floor + height * 0.33, depth * 0.43, this.surfaces.wood)
        this.lamp(parent, side * width * 0.3, floor + height * 0.5, depth * 0.46, 0.2)
      }
    }
    for (const x of [-width * 0.46, width * 0.46]) for (const z of [-depth * 0.43, depth * 0.43]) {
      this.cylinder(parent, 0.1, 0.12, height, x, floor + height / 2, z, this.surfaces.wood)
      this.box(parent, 0.32, 0.15, 0.32, x, floor + 0.05, z, this.surfaces.stone)
    }
    this.box(parent, width, 0.18, depth * 0.95, 0, floor + height, 0, this.surfaces.wood)
    this.roof(parent, width + 0.85, depth + 0.85, floor + height + 0.1, Math.min(width, depth) * 0.28)
  }

  private hall(parent: THREE.Object3D, building: Building) {
    const { width: w, depth: d, id } = building
    this.foundation(parent, w, d)
    const height = id === 'main_hall' ? 2.65 : 2.15
    this.pavilion(parent, w, d, height)
    if (id === 'main_hall') {
      this.pavilion(parent, w * 0.54, d * 0.55, 1.3, height + 1.65)
      for (const side of [-1, 1]) this.cylinder(parent, 0.16, 0.25, 0.7, side * (w / 2 + 0.25), 0.8, d * 0.35, this.gold)
    } else {
      for (const side of [-1, 1]) {
        const scroll = this.box(parent, 0.4, 1.1, 0.12, side * w * 0.3, 1.35, d * 0.46, this.surfaces.jade)
        scroll.rotation.z = side * 0.04
        this.box(parent, 0.48, 0.1, 0.18, side * w * 0.3, 1.9, d * 0.46, this.gold)
      }
    }
  }

  private tower(parent: THREE.Object3D, building: Building) {
    const size = Math.min(building.width, building.depth)
    this.foundation(parent, size, size)
    for (let floor = 0; floor < 5; floor++) {
      const width = size * (0.87 - floor * 0.11)
      const bottom = 0.45 + floor * 1.22
      this.cylinder(parent, width * 0.47, width * 0.49, 0.92, 0, bottom + 0.46, 0, this.surfaces.jade)
      this.box(parent, width * 0.18, 0.52, 0.06, 0, bottom + 0.4, width * 0.48, this.dark)
      this.roof(parent, width + 0.72, width + 0.72, bottom + 0.92, 0.56)
      this.lamp(parent, 0, bottom + 0.43, width * 0.5, 0.15)
    }
    this.cylinder(parent, 0, 0.17, 1.0, 0, 7.25, 0, this.gold)
  }

  private furnace(parent: THREE.Object3D, x: number, z: number, golden: boolean) {
    const material = golden ? this.gold : this.dark
    for (const angle of [0, Math.PI * 2 / 3, Math.PI * 4 / 3]) this.cylinder(parent, 0.14, 0.2, 0.7, x + Math.cos(angle) * 0.5, 0.79, z + Math.sin(angle) * 0.5, material)
    this.cylinder(parent, 0.72, 0.55, 1.0, x, 1.35, z, material, 12)
    this.cylinder(parent, 0.84, 0.84, 0.12, x, 1.88, z, this.gold, 12)
    if (golden) {
      this.cylinder(parent, 0.12, 0.78, 0.5, x, 2.14, z, this.gold, 12)
      this.cylinder(parent, 0.09, 0.14, 0.25, x, 2.5, z, this.dark)
    } else {
      const fire = this.cylinder(parent, 0.64, 0.64, 0.06, x, 1.95, z, this.glow, 12)
      fire.userData.cityLamp = true
      fire.castShadow = false
      this.lamps.push(fire)
      this.box(parent, 0.5, 2.8, 0.6, x + 0.85, 2.1, z - 0.4, this.surfaces.stone)
      this.box(parent, 0.68, 0.15, 0.78, x + 0.85, 3.52, z - 0.4, this.dark)
    }
    this.lamp(parent, x, 1.15, z + 0.62, 0.3)
  }

  private workshop(parent: THREE.Object3D, building: Building) {
    const { width: w, depth: d } = building
    this.foundation(parent, w, d)
    const shelter = new THREE.Group()
    shelter.position.z = -d * 0.2
    parent.add(shelter)
    this.pavilion(shelter, w, d * 0.65, 2.3, 0.45, false)
    this.box(shelter, w * 0.86, 1.4, 0.2, 0, 1.15, -d * 0.28, this.surfaces.jade)
    this.furnace(parent, -0.35, d * 0.18, building.id === 'alchemy')
    const tableX = w * 0.32
    this.box(parent, 0.85, 0.18, 1.15, tableX, 1.28, d * 0.12, this.surfaces.wood)
    for (const z of [-0.3, 0.3]) this.box(parent, 0.12, 0.75, 0.12, tableX, 0.83, d * 0.12 + z, this.dark)
    this.cylinder(parent, 0.17, 0.22, 0.28, tableX, 1.51, d * 0.12, building.id === 'alchemy' ? this.gold : this.surfaces.stone)
  }

  private trainingCourt(parent: THREE.Object3D, building: Building) {
    const { width: w, depth: d } = building
    this.foundation(parent, w, d)
    this.cylinder(parent, w * 0.33, w * 0.33, 0.04, 0, 0.48, 0.2, this.dark, 16)
    this.cylinder(parent, w * 0.3, w * 0.3, 0.05, 0, 0.51, 0.2, this.surfaces.jade, 16)
    const shelter = new THREE.Group()
    shelter.position.z = -d * 0.32
    parent.add(shelter)
    this.pavilion(shelter, w * 0.9, d * 0.28, 1.9, 0.45, false)
    for (const side of [-1, 1]) {
      this.cylinder(parent, 0.1, 0.13, 1.25, side * w * 0.35, 1.1, d * 0.22, this.surfaces.wood)
      this.box(parent, 0.7, 0.1, 0.1, side * w * 0.35, 1.35, d * 0.22, this.surfaces.wood)
      this.box(parent, 0.12, 2.2, 0.12, side * w * 0.46, 1.56, -d * 0.2, this.dark)
      this.box(parent, 0.72, 0.85, 0.04, side * (w * 0.46 - 0.32), 2.05, -d * 0.2, this.surfaces.roof)
    }
  }

  private dock(parent: THREE.Object3D, building: Building) {
    const { width: w, depth: d } = building
    this.box(parent, w + 0.5, 0.34, d + 0.5, 0, 0.2, 0, this.surfaces.wood)
    for (const x of [-w * 0.46, w * 0.46]) for (const z of [-d * 0.45, d * 0.45]) this.cylinder(parent, 0.16, 0.2, 1.45, x, 0.12, z, this.surfaces.wood)
    const shelter = new THREE.Group()
    shelter.position.z = -d * 0.22
    parent.add(shelter)
    this.pavilion(shelter, w * 0.68, d * 0.55, 2.05, 0.38, false)
    this.lamp(shelter, 0, 1.9, 0, 0.32)
    const boat = new THREE.Group()
    boat.position.set(w * 0.67, -0.1, d * 0.3)
    boat.rotation.y = -0.2
    parent.add(boat)
    const hull = this.cylinder(boat, 1, 0.7, 0.55, 0, 0, 0, this.surfaces.wood, 8)
    hull.scale.set(0.6, 1, 1.65)
    this.box(boat, 0.1, 2.85, 0.1, 0, 1.35, 0, this.dark)
    const sail = this.box(boat, 1.4, 1.8, 0.04, 0.15, 1.95, 0, this.surfaces.jade)
    sail.rotation.y = 0.25
    for (const y of [1.15, 1.65, 2.15, 2.65]) this.box(boat, 1.5, 0.045, 0.07, 0.15, y, 0, this.surfaces.wood)
  }

  private ground() {
    this.surfaces.grass.map!.repeat.set(8, 8)
    this.worldGround = this.mesh(this.group, this.geometry(new THREE.PlaneGeometry(320, 320)), this.surfaces.grass, 0, -0.08, 0)
    this.worldGround.rotation.x = -Math.PI / 2
    this.worldGround.castShadow = false
    this.worldGround.receiveShadow = true
    this.worldGround.userData.worldGround = true
    this.box(this.group, 11, 0.12, 7, 0, 0.05, 1.8, this.surfaces.jade)
    const seal = this.cylinder(this.group, 1.8, 1.8, 0.035, 0, 0.13, 1.8, this.dark, 24)
    this.cylinder(this.group, 1.64, 1.64, 0.04, 0, 0.15, 1.8, this.surfaces.jade, 24)
    seal.receiveShadow = true
    for (const building of CITY_BUILDINGS) {
      const z = building.z + building.depth / 2 + 0.55
      const dx = building.x, dz = z - 1.8
      const path = this.box(this.group, 1.45, 0.09, Math.hypot(dx, dz), dx / 2, 0.04, 1.8 + dz / 2, this.surfaces.jade)
      path.rotation.y = Math.atan2(dx, dz)
    }
    for (const [x, z, rotation] of [[0, -42, 0], [0, 43, 0], [-42, 1.8, Math.PI / 2], [42, 1.8, Math.PI / 2]]) {
      const road = this.box(this.group, 1.65, 0.09, 72, x, -0.005, z, this.surfaces.jade)
      road.rotation.y = rotation
    }
    for (let i = 0; i < 22; i++) {
      const angle = i * 2.39996
      const x = Math.cos(angle) * (15 + (i % 3)), z = Math.sin(angle) * (9.4 + (i % 2))
      if (CITY_BUILDINGS.some(b => Math.abs(x - b.x) < b.width / 2 + 1.1 && Math.abs(z - b.z) < b.depth / 2 + 1.1)) continue
      this.tree(x, z, i)
    }
    const groves = [[-25, -18], [25, -19], [-25, 20], [25, 21]] as const
    for (const [groveIndex, [cx, cz]] of groves.entries()) {
      for (let i = 0; i < 7; i++) {
        const angle = i * 2.39996 + groveIndex * 0.7
        const radius = 2.3 + (i % 3) * 1.25
        const x = cx + Math.cos(angle) * radius
        const z = cz + Math.sin(angle) * radius
        if (Math.abs(x) < 3.2 || Math.abs(z - 1.8) < 3.2) continue
        if (CITY_BUILDINGS.some(building => Math.abs(x - building.x) < building.width / 2 + 1 && Math.abs(z - building.z) < building.depth / 2 + 1)) continue
        this.tree(x, z, 22 + groveIndex * 7 + i)
      }
    }
    for (const side of [-1, 1]) for (const z of [-1.6, 5.2]) {
      const x = side * 5.3
      this.box(this.group, 0.45, 0.22, 0.45, x, 0.18, z, this.surfaces.stone)
      this.box(this.group, 0.18, 0.7, 0.18, x, 0.62, z, this.surfaces.jade)
      this.box(this.group, 0.55, 0.38, 0.5, x, 1.14, z, this.dark)
      this.lamp(this.group, x, 1.15, z + 0.255, 0.24)
      this.box(this.group, 0.7, 0.14, 0.65, x, 1.4, z, this.surfaces.roof)
    }
  }

  private tree(x: number, z: number, variant: number) {
    const tree = new THREE.Group()
    tree.position.set(x, 0, z)
    this.group.add(tree)
    const height = 1.8 + (variant % 3) * 0.4
    this.cylinder(tree, 0.09, 0.18, height, 0, height / 2, 0, this.surfaces.wood)
    for (let tier = 0; tier < 3; tier++) {
      const crown = this.mesh(tree, this.geometry(new THREE.ConeGeometry(1.18 - tier * 0.22, 1.35, 7)), this.foliage, 0, height * 0.65 + tier * 0.66, 0)
      crown.rotation.y = variant + tier * 0.3
    }
    if (variant % 4 === 0) {
      const rock = this.mesh(tree, this.geometry(new THREE.DodecahedronGeometry(0.55)), this.surfaces.stone, 0.6, 0.25, 0.4)
      rock.scale.set(1.2, 0.7, 0.9)
    }
  }

  private compact(parent: THREE.Group) {
    parent.updateMatrixWorld(true)
    const inverse = parent.matrixWorld.clone().invert()
    const buckets = new Map<THREE.Material, THREE.BufferGeometry[]>()
    const originals: THREE.Mesh[] = []
    parent.traverse(object => {
      if (!(object instanceof THREE.Mesh) || object.userData.cityLamp || object.userData.worldGround || Array.isArray(object.material)) return
      const geometry = (object.geometry.index ? object.geometry.toNonIndexed() : object.geometry.clone())
        .applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse, object.matrixWorld))
      const list = buckets.get(object.material) ?? []
      list.push(geometry)
      buckets.set(object.material, list)
      originals.push(object)
    })
    for (const [material, geometries] of buckets) {
      const merged = mergeGeometries(geometries, false)
      for (const geometry of geometries) geometry.dispose()
      if (merged) this.mesh(parent, this.geometry(merged), material, 0, 0, 0)
    }
    for (const mesh of originals) mesh.removeFromParent()
  }

  build() {
    this.group.name = 'sect-hd2d-environment'
    this.ground()
    this.compact(this.group)
    for (const building of CITY_BUILDINGS) {
      const group = new THREE.Group()
      group.name = building.id
      group.userData.buildingId = building.id
      group.position.set(building.x, 0, building.z)
      this.group.add(group)
      if (building.id === 'tower') this.tower(group, building)
      else if (building.id === 'forge' || building.id === 'alchemy') this.workshop(group, building)
      else if (building.id === 'drill') this.trainingCourt(group, building)
      else if (building.id === 'dock') this.dock(group, building)
      else this.hall(group, building)
      this.compact(group)
      this.buildings.set(building.id, group)
    }
    return { group: this.group, buildings: this.buildings, lamps: this.lamps, ground: this.worldGround, dispose: () => this.dispose() }
  }

  private dispose() {
    for (const geometry of this.geometries) geometry.dispose()
    for (const material of this.materials) material.dispose()
    for (const texture of this.textures) texture.dispose()
    this.group.clear()
    this.buildings.clear()
    this.lamps.length = 0
  }
}

export function buildCityEnvironment() {
  return new CityBuilder().build()
}
