<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import type { BattleEvent, BattleUnit } from './battlePlayback'
import { effectLabel } from './battlePlayback'
import { createBattleScene, type BattleSceneLabel, type BattleSceneState } from './battleScene'

const props = defineProps<{ units: BattleUnit[]; event: BattleEvent | null; phase: BattleSceneState['phase']; playing: boolean; reduced: boolean }>()
const emit = defineEmits<{ ready: [value: boolean]; select: [id: string] }>()
const host = ref<HTMLElement | null>(null)
const labels = shallowRef<BattleSceneLabel[]>([])
const failed = ref(false)
let scene: ReturnType<typeof createBattleScene> | undefined
function snapshot(): BattleSceneState { return { units: props.units, event: props.event, phase: props.phase, playing: props.playing, reduced: props.reduced } }
function fail() { scene?.dispose(); scene = undefined; failed.value = true; emit('ready', false) }
function unit(id: string) { return props.units.find(item => item.id === id) }
function effects(id: string) { return props.playing && props.phase !== 'windup' ? props.event?.effects.filter(effect => effect.target_id === id) ?? [] : [] }
watch(() => [props.units, props.event, props.phase, props.playing, props.reduced], () => { scene?.update(snapshot()) }, { flush: 'post' })
onMounted(() => {
  if (!host.value) return
  try {
    scene = createBattleScene(host.value, { labels: value => { labels.value = value }, select: id => emit('select', id), failure: fail })
    scene.update(snapshot())
    emit('ready', true)
  } catch { scene?.dispose(); scene = undefined; fail() }
})
onUnmounted(() => { scene?.dispose(); scene = undefined })
</script>
<template>
  <section v-if="!failed" class="battle-arena" aria-label="立体交锋战场">
    <div ref="host" class="arena-canvas"></div>
    <div class="arena-labels" aria-hidden="true"><div v-for="label in labels.filter(item=>item.visible)" :key="label.id" class="arena-unit-label" :class="{enemy:unit(label.id)?.side==='enemy',fallen:unit(label.id)?.hp===0}" :style="{left:`${label.x}px`,top:`${label.y}px`}"><strong>{{ unit(label.id)?.name }}</strong><div class="arena-hp"><i :style="{width:`${(unit(label.id)?.hp??0)/Math.max(1,unit(label.id)?.max_hp??1)*100}%`}"></i></div><div v-if="effects(label.id).length" :key="`${event?.sequence}-${label.id}`" class="arena-effects"><span v-for="(effect,index) in effects(label.id)" :key="index" :class="effect.kind">{{ effectLabel(effect) }}</span></div></div></div>
    <p class="arena-action" role="status">{{ playing && event ? `${units.find(item=>item.id===event?.actor_id)?.name??''} · ${event.skill_name}` : '点选人物或下方姓名查看状态' }}</p>
  </section>
  <p v-else class="arena-failure" role="status">立体战场暂时无法显示，下方保留真实角色状态与完整战报。</p>
</template>
<style scoped>
.battle-arena{position:relative;height:350px;isolation:isolate;background:radial-gradient(ellipse at 50% 74%,#dfe5cd88,transparent 72%);border-block:1px solid #c7cdb34d}.arena-canvas{position:absolute;inset:0}.arena-canvas :deep(canvas){display:block;width:100%;height:100%;cursor:pointer}.arena-labels{position:absolute;inset:0;pointer-events:none}.arena-unit-label{position:absolute;transform:translate(-50%,-100%);min-width:50px;max-width:94px;text-align:center;color:#254f3b}.arena-unit-label>strong{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font:12px 'SimSun',serif;text-shadow:0 1px #fff8e2,1px 0 #fff8e2,-1px 0 #fff8e2}.arena-unit-label.enemy{color:#795638}.arena-unit-label.fallen{opacity:.6}.arena-hp{height:3px;width:36px;margin:4px auto 0;background:#bdc5ad;box-shadow:0 0 0 1px #f6f1dfb0}.arena-hp>i{display:block;height:100%;background:#477a54}.enemy .arena-hp>i{background:#9e6e4e}.arena-effects{position:absolute;left:50%;top:0;display:grid;gap:3px;transform:translate(-50%,-100%);animation:impact-number .4s ease-out both;font:700 15px 'Microsoft YaHei',sans-serif;white-space:nowrap;color:#9c3f2f;text-shadow:0 1px #fff9e7,1px 0 #fff9e7,-1px 0 #fff9e7}.arena-effects .heal{color:#2b744e}.arena-effects .shield{color:#377188}.arena-effects .buff{color:#957435}.arena-action{position:absolute;bottom:7px;left:0;right:0;margin:0;text-align:center;color:#4d644a;font-size:11px;pointer-events:none}.arena-failure{position:relative;padding:12px 16px;font-size:12px;color:var(--muted)}@keyframes impact-number{from{opacity:0;translate:0 8px;scale:1.15}25%{opacity:1}to{opacity:1;translate:0 -10px;scale:1}}@media(max-width:640px){.battle-arena{height:290px}.arena-unit-label{max-width:62px;min-width:36px}.arena-unit-label>strong{font-size:11px}.arena-hp{width:28px}.arena-effects{font-size:13px}.arena-action{font-size:10px}}@media(prefers-reduced-motion:reduce){.arena-effects{animation:none}}
</style>
