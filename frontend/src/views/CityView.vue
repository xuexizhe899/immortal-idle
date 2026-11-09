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
      @click="spot.panel === 'tower' ? enterTower() : open(spot.panel)"
    >
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

.hotspot:hover {
  border-color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.14);
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
