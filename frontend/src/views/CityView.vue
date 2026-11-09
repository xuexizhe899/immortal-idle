<script setup lang="ts">
import { computed, ref } from 'vue'

import PanelModal from '../components/PanelModal.vue'
import { useGameStore } from '../stores/game'
import CodexPanel from './CodexPanel.vue'
import CraftPanel from './CraftPanel.vue'
import DutyPanel from './DutyPanel.vue'
import SectPanel from './SectPanel.vue'

const TITLES: Record<string, string> = {
  codex: '藏经阁',
  sect: '宗门主殿',
  expedition: '远行码头',
  duty: '演武场',
  forge: '炼器炉',
  alchemy: '炼丹房',
}

const store = useGameStore()
const openPanel = ref<string | null>(null)

const city = computed(() => store.catalog?.city)
const hotspots = computed(() => city.value?.hotspots ?? [])
const currentTitle = computed(() => TITLES[openPanel.value ?? ''] ?? '')

function open(panel: string) {
  openPanel.value = panel
}

function hideBroken(event: Event) {
  const image = event.target as HTMLImageElement
  image.style.display = 'none'
}

async function enterTower() {
  if (store.party.length === 0) {
    open('codex')
    return
  }
  await store.startRun(store.party)
}
</script>

<template>
  <div v-if="city" class="city" :style="{ aspectRatio: String(city.aspect) }">
    <img :src="city.background" alt="宗门主城" class="bg" />

    <button
      v-for="spot in hotspots"
      :key="spot.id"
      class="hotspot"
      type="button"
      :style="{
        left: `${spot.x}%`,
        top: `${spot.y}%`,
        width: `${spot.w}%`,
        height: `${spot.h}%`,
      }"
      :aria-label="spot.name"
      @click="spot.panel === 'tower' ? enterTower() : open(spot.panel)"
    >
      <img
        v-if="spot.sprite"
        :src="spot.sprite"
        :alt="spot.name"
        class="building"
        :class="spot.anim ? `anim-${spot.anim}` : ''"
        draggable="false"
        @error="hideBroken"
      />
      <span v-if="spot.anim === 'alchemy' || spot.anim === 'forge'" class="smoke" aria-hidden="true">
        <i></i><i></i><i></i>
      </span>
      <span class="tag">{{ spot.name }}</span>
    </button>

    <div class="hud">
      <span>修为 {{ (store.resources?.cultivation ?? 0).toFixed(0) }}</span>
      <span>灵石 {{ (store.resources?.spirit_stone ?? 0).toFixed(0) }}</span>
      <span>行动力 {{ (store.resources?.stamina ?? 0).toFixed(0) }}</span>
      <span>声望 {{ (store.resources?.reputation ?? 0).toFixed(0) }}</span>
      <span class="party">队伍 {{ store.party.length }} / 5</span>
    </div>
  </div>

  <PanelModal v-if="openPanel" :title="currentTitle" @close="openPanel = null">
    <CodexPanel v-if="openPanel === 'codex'" />
    <SectPanel v-else-if="openPanel === 'sect'" />
    <DutyPanel v-else-if="openPanel === 'duty'" />
    <CraftPanel v-else-if="openPanel === 'alchemy'" kind="pill" />
    <CraftPanel v-else-if="openPanel === 'forge'" kind="artifact" />
    <p v-else class="hint">远行尚未开放，先把宗门经营起来。</p>
  </PanelModal>
</template>

<style scoped>
.city {
  position: relative;
  width: 100%;
  max-width: calc((100vh - 180px) * 1.5);
  margin: 0 auto;
  aspect-ratio: 1.5;
  border: 2px solid var(--border);
  background: #bcd7e6;
  box-shadow: 5px 5px 0 rgba(20, 20, 26, 0.25);
  overflow: hidden;
}

.bg {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  image-rendering: pixelated;
}

.hotspot {
  position: absolute;
  transform: translate(-50%, -50%);
  padding: 0;
  border: 2px solid transparent;
  background: transparent;
  cursor: pointer;
}

.hotspot:focus-visible {
  outline: none;
}

.building {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  image-rendering: pixelated;
  pointer-events: none;
}

.hotspot:hover .building,
.hotspot:focus-visible .building {
  filter: brightness(1.14) drop-shadow(0 0 6px rgba(255, 246, 214, 0.85));
}

/* 每栋建筑的常驻动效：幅度小、周期错开，避免整屏齐步走 */
.anim-library {
  animation: breathe 5.2s ease-in-out infinite;
}

.anim-sect {
  animation: lantern 3.4s ease-in-out infinite;
}

.anim-dock {
  animation: bob 4.6s ease-in-out infinite;
}

.anim-tower {
  animation: glow 6s ease-in-out infinite;
}

.anim-duty {
  animation: sway 3.8s ease-in-out infinite;
  transform-origin: center bottom;
}

.anim-forge {
  animation: flicker 1.7s steps(3) infinite;
}

.anim-alchemy {
  animation: breathe 4.4s ease-in-out infinite 0.8s;
}

@keyframes breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

@keyframes lantern {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.14) saturate(1.08); }
}

@keyframes bob {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-3px) rotate(-0.6deg); }
}

@keyframes glow {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.1) drop-shadow(0 0 6px rgba(140, 220, 200, 0.55)); }
}

@keyframes sway {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(0.5deg); }
}

@keyframes flicker {
  0%, 100% { filter: brightness(1); }
  40% { filter: brightness(1.16) saturate(1.15); }
  70% { filter: brightness(0.96); }
}

/* 丹房/锻炉的烟：三个像素点错峰上升 */
.smoke {
  position: absolute;
  left: 50%;
  top: 6%;
  width: 0;
  height: 0;
  pointer-events: none;
}

.smoke i {
  position: absolute;
  width: 5px;
  height: 5px;
  background: rgba(230, 230, 224, 0.85);
  animation: rise 2.8s linear infinite;
}

.smoke i:nth-child(2) {
  animation-delay: 0.9s;
  left: 4px;
}

.smoke i:nth-child(3) {
  animation-delay: 1.8s;
  left: -4px;
}

@keyframes rise {
  0% { transform: translateY(0); opacity: 0; }
  15% { opacity: 0.9; }
  100% { transform: translateY(-26px); opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .building,
  .smoke i {
    animation: none;
  }
}

.tag {
  position: absolute;
  left: 50%;
  bottom: -22px;
  transform: translateX(-50%);
  padding: 1px 8px;
  background: rgba(20, 20, 26, 0.84);
  color: #f4eede;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.12s ease;
}

.hotspot:hover .tag {
  opacity: 1;
}

.hud {
  position: absolute;
  left: 0;
  top: 0;
  display: flex;
  gap: 14px;
  padding: 7px 14px;
  background: rgba(20, 20, 26, 0.74);
  color: #f4eede;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
}

.hud .party {
  color: #f0c674;
}

.hint {
  color: var(--muted);
  font-size: 13px;
}
</style>
