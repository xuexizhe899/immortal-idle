import { computed, onMounted, onUnmounted, ref } from 'vue'

export type DayPhase = 'dawn' | 'day' | 'dusk' | 'night'
export const phases: { id: DayPhase; name: string; hour: number }[] = [
  { id: 'dawn', name: '晨曦', hour: 6 },
  { id: 'day', name: '晴昼', hour: 12 },
  { id: 'dusk', name: '薄暮', hour: 18 },
  { id: 'night', name: '月夜', hour: 23 },
]

const keyframes = [
  { hour: 0, brightness: .74, saturation: .76, night: .62, warmth: 0 },
  { hour: 5, brightness: .76, saturation: .78, night: .56, warmth: .08 },
  { hour: 6.5, brightness: .86, saturation: .86, night: .18, warmth: .25 },
  { hour: 8, brightness: 1, saturation: 1, night: 0, warmth: .02 },
  { hour: 16, brightness: 1, saturation: 1, night: 0, warmth: .02 },
  { hour: 18, brightness: .82, saturation: .9, night: .18, warmth: .36 },
  { hour: 19.5, brightness: .76, saturation: .78, night: .56, warmth: .06 },
  { hour: 24, brightness: .74, saturation: .76, night: .62, warmth: 0 },
]

export function lightingAt(hour: number) {
  const wrapped = ((hour % 24) + 24) % 24
  const index = keyframes.findIndex(frame => frame.hour > wrapped)
  const start = keyframes[index - 1]!
  const end = keyframes[index]!
  const ratio = (wrapped - start.hour) / (end.hour - start.hour)
  const mix = (key: 'brightness' | 'saturation' | 'night' | 'warmth') =>
    start[key] + (end[key] - start[key]) * ratio
  const phase: DayPhase = wrapped >= 5 && wrapped < 8 ? 'dawn'
    : wrapped >= 8 && wrapped < 17 ? 'day'
      : wrapped >= 17 && wrapped < 19.5 ? 'dusk' : 'night'
  return { phase, brightness: mix('brightness'), saturation: mix('saturation'), night: mix('night'), warmth: mix('warmth') }
}

export function useDayCycle() {
  const now = ref(new Date())
  const selection = ref<'auto' | DayPhase>('auto')
  let timer: ReturnType<typeof setInterval> | undefined
  const update = () => { now.value = new Date() }
  onMounted(() => {
    timer = setInterval(update, 30_000)
    document.addEventListener('visibilitychange', update)
  })
  onUnmounted(() => {
    clearInterval(timer)
    document.removeEventListener('visibilitychange', update)
  })
  const lighting = computed(() => lightingAt(selection.value === 'auto'
    ? now.value.getHours() + now.value.getMinutes() / 60
    : phases.find(phase => phase.id === selection.value)!.hour))
  const phaseName = computed(() => phases.find(phase => phase.id === lighting.value.phase)!.name)
  const sceneStyle = computed(() => ({
    '--day-brightness': String(lighting.value.brightness),
    '--day-saturation': String(lighting.value.saturation),
    '--night-opacity': String(lighting.value.night),
    '--warm-opacity': String(lighting.value.warmth),
    '--lantern-opacity': String(Math.min(1, lighting.value.night * 1.5)),
  }))
  return { selection, phaseName, sceneStyle }
}
