<script setup lang="ts">
import type { Application, Container, Sprite } from 'pixi.js'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { BattleResult } from '../api/client'

const props = defineProps<{ party: { id: string; name: string; image: string }[]; result: BattleResult | null; hp: number; maxHp: number }>()
const emit = defineEmits<{ playing: [value: boolean] }>()
const host = ref<HTMLDivElement | null>(null)
const failed = ref(false)
const playing = ref(false)
const names = computed(() => props.party.map(disciple => disciple.name).join(' · '))
let app: Application | null = null
let partyLayer: Container | null = null
let enemyLayer: Container | null = null
let disposed = false
let ready = false
let generation = 0
let elapsed = 0
let playbackToken = 0
let watchdog: number | undefined

function clearWatchdog() {
  if (watchdog !== undefined) window.clearTimeout(watchdog)
  watchdog = undefined
}

function finish() {
  clearWatchdog()
  playbackToken += 1
  playing.value = false
  emit('playing', false)
  app?.ticker.stop()
  if (partyLayer) partyLayer.x = 0
  if (enemyLayer) {
    enemyLayer.x = 0
    enemyLayer.alpha = props.result && !props.result.won ? 1 : .55
  }
  if (ready && !disposed) app?.render()
}

async function redraw() {
  const renderer = app
  if (!renderer || !partyLayer || !enemyLayer) return
  const token = ++generation
  const { Assets, Sprite, Graphics } = await import('pixi.js')
  if (disposed || token !== generation) return
  partyLayer.removeChildren().forEach(child => child.destroy())
  enemyLayer.removeChildren().forEach(child => child.destroy())
  const size = props.party.length > 3 ? 100 : 125
  const spacing = props.party.length > 3 ? 70 : 90
  await Promise.all(props.party.map(async (disciple, index) => {
    try {
      const texture = await Assets.load(disciple.image)
      if (disposed || token !== generation || !partyLayer) return
      const sprite: Sprite = new Sprite(texture)
      sprite.anchor.set(.5, 1)
      sprite.height = size
      sprite.width = size * (texture.width / texture.height)
      sprite.x = 95 + index * spacing
      sprite.y = 215
      partyLayer.addChild(sprite)
    } catch {
      failed.value = true
      finish()
    }
  }))
  if (disposed || token !== generation || !enemyLayer) return
  const enemy = new Graphics()
  enemy.poly([0, -92, 20, -75, 35, -40, 28, -2, -28, -2, -35, -40, -20, -75]).fill(0x40584b)
  enemy.poly([0, -92, 9, -79, -9, -79]).fill(0xb9a56f)
  enemy.rect(-13, -63, 26, 5).fill(0xb89b60)
  enemy.poly([-28, -50, -52, -4, -40, 0, -17, -29]).fill(0x344b40)
  enemy.poly([28, -50, 52, -4, 40, 0, 17, -29]).fill(0x344b40)
  enemy.x = 735
  enemy.y = 211
  enemyLayer.addChild(enemy)
  renderer.render()
}

function play() {
  if (!props.result || disposed) return
  clearWatchdog()
  const token = ++playbackToken
  elapsed = 0
  if (failed.value || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    finish()
    return
  }
  playing.value = true
  emit('playing', true)
  // Rendering and assets may still be loading; this always releases the controls.
  watchdog = window.setTimeout(() => {
    if (!disposed && token === playbackToken) finish()
  }, 2200)
  if (ready && !document.hidden) app?.ticker.start()
}

function visibility() {
  if (document.hidden) app?.ticker.stop()
  else if (ready && playing.value) app?.ticker.start()
}

onMounted(async () => {
  document.addEventListener('visibilitychange', visibility)
  try {
    const { Application, Container, Graphics } = await import('pixi.js')
    if (disposed) return
    const renderer = new Application()
    await renderer.init({ width: 900, height: 260, backgroundAlpha: 0, antialias: false, autoStart: false, resolution: Math.min(window.devicePixelRatio || 1, 2) })
    if (disposed) {
      renderer.destroy(true, { children: true })
      return
    }
    app = renderer
    host.value?.appendChild(renderer.canvas)
    const floor = new Graphics()
    floor.ellipse(450, 220, 420, 30).fill({ color: 0x567257, alpha: .14 })
    floor.moveTo(60, 220).lineTo(840, 220).stroke({ color: 0x93a17c, width: 1 })
    renderer.stage.addChild(floor)
    partyLayer = new Container()
    enemyLayer = new Container()
    renderer.stage.addChild(partyLayer, enemyLayer)
    await redraw()
    if (disposed) return
    renderer.ticker.add(ticker => {
      if (!playing.value || document.hidden) return
      elapsed += ticker.deltaMS
      const progress = Math.min(elapsed / 1550, 1)
      if (partyLayer) partyLayer.x = progress < .5 ? Math.sin(progress * Math.PI * 2) * 32 : 0
      if (enemyLayer) {
        enemyLayer.x = progress > .35 && progress < .75 ? Math.sin(progress * 70) * 4 : 0
        enemyLayer.alpha = props.result?.won && progress > .6 ? Math.max(.15, 1 - (progress - .6) * 2) : 1
      }
      if (progress >= 1) finish()
    })
    ready = true
    if (playing.value && !document.hidden) renderer.ticker.start()
    else renderer.ticker.stop()
    renderer.render()
  } catch {
    failed.value = true
    finish()
  }
})

watch(() => props.party.map(disciple => disciple.id).join(','), () => {
  void redraw().catch(() => { failed.value = true; finish() })
})
watch(() => props.result?.id, (id, previous) => { if (id && id !== previous) play() })
onUnmounted(() => {
  disposed = true
  ready = false
  generation += 1
  playbackToken += 1
  clearWatchdog()
  document.removeEventListener('visibilitychange', visibility)
  app?.destroy(true, { children: true })
  app = null
})
</script>
<template><div class="battle-stage"><img class="stage-scene pixel-art" src="/assets/trial-v03/scene_tower_trial.png" alt="" draggable="false" /><div class="stage-atmosphere"></div><div class="stage-caption"><span class="eyebrow">问道塔 · 石阶试炼</span><span class="stage-hint">{{ playing?'交锋中…':result?(result.won?'此战获胜':'此战失利'):'同道已集结，静候前行' }}</span></div><div ref="host" class="canvas-host" :class="{fallback:failed}" aria-hidden="true"></div><div v-if="failed" class="fallback-party"><img v-for="d in party" :key="d.id" :src="d.image" alt="" class="pixel-art" /><span>守塔灵卫</span></div><div class="battle-names"><span>{{ names }}</span><span>守塔灵卫</span></div><div v-if="result" class="battle-report" aria-live="polite"><span :class="result.won?'won':'lost'">{{ result.won?'胜':'败' }}</span><span>队伍战力 <b>{{ result.party_power.toFixed(1) }}</b></span><span>敌方战力 <b>{{ result.enemy_power }}</b></span><span>气血损失 <b>{{ result.damage }}</b></span><button v-if="playing" class="btn btn-small" @click="finish">跳过演出</button></div><p v-else class="stage-bottom">选择前方路线，开始此次试炼。</p></div></template>
<style scoped>
.battle-stage{position:relative;overflow:hidden;min-height:270px;background:linear-gradient(#d4dfca,#f0eddc 55%,#c9d2b8);border:1px solid #b7bba0}.stage-scene{position:absolute;inset:0;width:100%;height:calc(100% - 55px);object-fit:cover;object-position:center 66%;pointer-events:none}.stage-atmosphere{position:absolute;inset:0;pointer-events:none;background:linear-gradient(145deg,transparent 50%,#acbfa28c 50%,transparent 70%),linear-gradient(25deg,#839c7c35 10%,transparent 10%);opacity:.15}.stage-caption{position:absolute;left:20px;right:20px;top:17px;display:flex;justify-content:space-between;gap:10px;z-index:1}.stage-caption>.eyebrow{padding:3px 7px;background:#f8f0dadb;color:#47613f;font-size:8px}.stage-hint{font-size:10px;color:#42593a;padding:3px 7px;background:#f8f0dadb}.canvas-host{position:relative;width:100%;aspect-ratio:900 / 260;min-height:200px;display:flex;align-items:flex-end}.canvas-host:deep(canvas){display:block;width:100%;height:auto;image-rendering:pixelated}.battle-names{position:relative;text-shadow:0 1px 2px #fff6d9;display:flex;justify-content:space-between;padding:0 12% 16px;font-size:10px;color:#506748}.battle-report{position:relative;display:flex;align-items:center;gap:22px;padding:12px 20px;background:#f5efdfe0;border-top:1px solid #b9baa0;font-size:10px;color:var(--muted);min-height:55px}.battle-report b{color:var(--ink);font-weight:500;margin-left:5px}.battle-report>.won,.battle-report>.lost{font:20px 'SimSun',serif;color:var(--jade);width:28px}.battle-report>.lost{color:var(--danger)}.battle-report>.btn{margin-left:auto;min-height:30px;font-size:10px}.stage-bottom{position:relative;text-align:center;font-size:11px;color:var(--muted);margin:0;padding:12px;background:#f5efdfe0;border-top:1px solid #b9baa0}.fallback-party{display:flex;position:absolute;inset:50px 8% 60px;align-items:flex-end;pointer-events:none}.fallback-party img{width:16%;max-height:130px;object-fit:contain}.fallback-party>span{margin-left:auto;padding:40px 15px;background:#52694d;color:#f1e6c7;font-family:'SimSun',serif}.fallback{visibility:hidden}
@media(max-width:640px){.stage-caption{left:12px;right:12px;top:12px}.stage-hint{font-size:8px}.stage-caption>.eyebrow{font-size:7px}.canvas-host{min-height:140px}.battle-stage{min-height:220px}.battle-names{padding:0 8% 10px;font-size:8px}.battle-names>span:first-child{max-width:65%}.battle-report{padding:10px;gap:9px;flex-wrap:wrap;font-size:9px}.battle-report b{margin-left:2px}.battle-report>.won,.battle-report>.lost{width:20px;font-size:17px}.battle-report>.btn{width:100%;margin:0}.stage-bottom{font-size:10px}}
</style>
