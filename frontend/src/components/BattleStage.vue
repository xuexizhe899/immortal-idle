<script setup lang="ts">
import { Application, Container, Graphics } from 'pixi.js'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{ hp: number; maxHp: number; layer: number }>()

const host = ref<HTMLDivElement | null>(null)
let app: Application | null = null
let partyLayer: Container | null = null
let enemyLayer: Container | null = null
let tick = 0

function fighter(color: number, facing: number): Graphics {
  const unit = new Graphics()
  unit.rect(-9, -22, 18, 16).fill(color)
  unit.rect(-7, -34, 14, 12).fill(0xf0d8b8)
  unit.rect(-9, -10, 18, 4).fill(0x2b2b33)
  unit.rect(facing * 10, -26, 12, 3).fill(0x2b2b33)
  return unit
}

function redraw() {
  if (!partyLayer || !enemyLayer) return
  partyLayer.removeChildren()
  enemyLayer.removeChildren()

  for (let i = 0; i < 3; i += 1) {
    const unit = fighter(0x2f6f5e, 1)
    unit.x = 100 + i * 44
    unit.y = 140
    partyLayer.addChild(unit)
  }

  const count = Math.min(3, Math.floor(props.layer / 5) + 1)
  for (let i = 0; i < count; i += 1) {
    const unit = fighter(0x8f3b2d, -1)
    unit.x = 330 + i * 44
    unit.y = 140
    enemyLayer.addChild(unit)
  }
}

onMounted(async () => {
  app = new Application()
  await app.init({ width: 520, height: 170, background: '#f3eedf', antialias: false })
  host.value?.appendChild(app.canvas)

  partyLayer = new Container()
  enemyLayer = new Container()
  app.stage.addChild(partyLayer, enemyLayer)
  redraw()

  app.ticker.add(() => {
    tick += 0.05
    if (partyLayer) partyLayer.y = Math.sin(tick) * 2
    if (enemyLayer) enemyLayer.y = Math.cos(tick) * 2
  })
})

watch(() => props.layer, redraw)

onUnmounted(() => {
  app?.destroy(true, { children: true })
  app = null
})
</script>

<template>
  <div ref="host" class="stage"></div>
</template>

<style scoped>
.stage {
  width: 100%;
  margin-bottom: 12px;
  border: 2px solid var(--border);
  background: #f3eedf;
  overflow: hidden;
}

.stage :deep(canvas) {
  display: block;
  width: 100%;
  height: auto;
  image-rendering: pixelated;
}
</style>
