<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { CityActor } from './cityModel'
import type { createCityScene, SceneLabel, SceneLighting } from './cityScene'

const props = defineProps<{
  actors: CityActor[]
  buildings: { id: string; name: string; status: string }[]
  lighting: SceneLighting
}>()
const emit = defineEmits<{ building: [id: string]; disciple: [id: string] }>()
const viewport = ref<HTMLDivElement | null>(null)
const labels = ref<SceneLabel[]>([])
const loading = ref(true)
const error = ref('')
const imageFailure = ref(false)
const depth = ref(false)
const reduced = ref(false)
const revision = ref(0)
let scene: ReturnType<typeof createCityScene> | undefined
let mounted = false
let attempt = 0
const projected = computed(() => labels.value.map(label => ({ ...label, building: props.buildings.find(item => item.id === label.id) })).filter(item => item.building))
const actorStatus = (actor: CityActor) => `${actor.duty ? '正在值守' : '在宗门'}${actor.injured ? '，有伤在身' : ''}`

async function load() {
  const request = ++attempt
  scene?.dispose(); scene = undefined
  labels.value = []
  loading.value = true; error.value = ''; imageFailure.value = false
  try {
    const { createCityScene } = await import('./cityScene')
    if (!mounted || request !== attempt || !viewport.value) return
    scene = createCityScene(viewport.value, {
      select(kind, id) { if (kind === 'building') emit('building', id); else emit('disciple', id) },
      labels(items) { labels.value = items },
      imageFailure() { imageFailure.value = true },
      contextLost() { error.value = '场景暂时中断，可重新载入；下方功能入口仍可使用。' },
    })
    scene.updateLighting(props.lighting)
    scene.updateActors(props.actors)
    scene.setPreferences({ reduced: reduced.value, depth: depth.value })
  } catch {
    scene?.dispose(); scene = undefined
    error.value = '场景暂未载入，可重试或通过下方入口打理宗门。'
  } finally { if (mounted && request === attempt) loading.value = false }
}
watch(() => props.actors, actors => scene?.updateActors(actors))
watch(() => props.lighting, lighting => scene?.updateLighting(lighting))
watch([depth, reduced], () => scene?.setPreferences({ depth: depth.value, reduced: reduced.value }))
watch(revision, load)
let motion: MediaQueryList | undefined
const updateMotion = () => { reduced.value = motion?.matches ?? false }
onMounted(() => {
  mounted = true
  motion = matchMedia('(prefers-reduced-motion: reduce)')
  updateMotion(); motion.addEventListener('change', updateMotion)
  void load()
})
onUnmounted(() => { mounted = false; attempt++; scene?.dispose(); motion?.removeEventListener('change', updateMotion) })
</script>

<template>
  <div class="city-world">
    <div ref="viewport" class="world-viewport" tabindex="0" aria-label="宗门场景。拖动或方向键移动，滚轮或加减键缩放，Home复位。" />
    <div class="world-labels">
      <button v-for="label in projected" v-show="label.visible" :key="label.id" class="world-label"
        :class="{ tower: label.id === 'tower' }" :style="{ left: `${label.x}px`, top: `${label.y}px` }"
        :aria-label="`${label.building!.name}，${label.building!.status}`" @click="emit('building', label.id)">
        {{ label.building!.name }}
      </button>
    </div>
    <div class="world-tools" aria-label="场景视野">
      <button aria-label="放大宗门场景" @click="scene?.zoom(1.2)">＋</button>
      <button aria-label="缩小宗门场景" @click="scene?.zoom(1 / 1.2)">−</button>
      <button @click="scene?.reset()">复位</button>
      <label><input v-model="depth" type="checkbox" />柔景</label>
    </div>
    <details v-if="actors.length" class="world-residents">
      <summary>山中同道 · {{ actors.length }}</summary>
      <div><button v-for="actor in actors" :key="actor.id" :aria-label="`${actor.name}，${actorStatus(actor)}`" @click="emit('disciple', actor.id)"><span>{{ actor.name }}</span><small>{{ actorStatus(actor) }}</small></button></div>
    </details>
    <p v-if="loading" class="world-message" role="status">正在铺展山门…</p>
    <div v-else-if="error" class="world-message" role="alert"><p>{{ error }}</p><button class="btn btn-small" @click="revision++">重新载入</button></div>
    <p v-else-if="imageFailure" class="image-message" role="status">部分弟子形象尚未载入，可在“山中同道”查看。</p>
  </div>
</template>

<style scoped>
.city-world{position:absolute;inset:0;background:#c5d5c4}.world-viewport{position:absolute;inset:0;outline-offset:-4px}.world-viewport :deep(canvas){display:block;width:100%;height:100%;touch-action:none;cursor:grab}.world-viewport :deep(canvas:active){cursor:grabbing}.world-labels{position:absolute;inset:0;pointer-events:none;overflow:hidden}.world-label{position:absolute;transform:translate(-50%,-50%);pointer-events:auto;padding:5px 13px;border:1px solid #a18d5c;background:#f9f1dfe8;color:#355448;font:600 12px/1.4 'SimSun',serif;box-shadow:0 2px 0 #344b3829;white-space:nowrap}.world-label.tower{background:#2f5549ed;color:#fff0c6;border-color:#c4af75}.world-tools{position:absolute;left:16px;bottom:112px;display:flex;align-items:center;gap:2px;padding:3px;border:1px solid #adb18c;background:#f6f0deed}.world-tools button,.world-tools label{min-width:34px;min-height:36px;padding:7px;border:0;background:transparent;color:#3d5a48;font-size:12px}.world-tools label{display:flex;align-items:center;gap:4px;cursor:pointer}.world-tools input{accent-color:#3b6650}.world-residents{position:absolute;right:16px;top:80px;max-width:220px;padding:8px 12px;border:1px solid #b4b596;background:#f7f1e2eb;font-size:11px;color:#3c5a47}.world-residents summary{cursor:pointer;min-height:24px}.world-residents>div{max-height:min(260px,40dvh);overflow:auto}.world-residents button{display:flex;justify-content:space-between;gap:12px;width:100%;min-height:38px;padding:6px 0;border:0;border-top:1px solid #d5d2bc;background:transparent;color:inherit;text-align:left}.world-residents small{font-size:10px;color:#737c61}.world-message{position:absolute;left:50%;top:45%;transform:translate(-50%,-50%);width:min(330px,80%);padding:20px;text-align:center;background:#f7f0dfed;border:1px solid #b3b28f;color:#365344;font-size:13px}.image-message{position:absolute;top:80px;left:16px;max-width:220px;font-size:11px;background:#f7f0dfed;padding:8px;color:#54634e}@media(max-width:640px){.world-label{padding:6px 8px;font-size:11px;min-height:32px}.world-tools{left:12px;bottom:102px}.world-tools button,.world-tools label{min-height:40px}.world-residents{right:12px;top:72px;max-width:190px}.image-message{top:115px;max-width:165px;font-size:10px}}
</style>
