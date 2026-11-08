<script setup lang="ts">
import type { components } from '../generated/api'

type Disciple = components['schemas']['DiscipleState']

defineProps<{
  disciple: Disciple
  name: string
  selected: boolean
  disabled: boolean
}>()

defineEmits<{ toggle: [] }>()

function hideBroken(event: Event) {
  const image = event.target as HTMLImageElement
  image.style.display = 'none'
}
</script>

<template>
  <button
    class="card"
    :class="{ selected, disabled }"
    type="button"
    :disabled="disabled && !selected"
    @click="$emit('toggle')"
  >
    <div class="portrait">
      <span class="initial">{{ name.slice(0, 1) }}</span>
      <img
        :src="`/assets/${disciple.template_id}.png`"
        :alt="name"
        loading="lazy"
        @error="hideBroken"
      />
    </div>
    <div class="meta">
      <span class="name">{{ name }}</span>
      <span v-if="disciple.busy" class="tag busy">出征中</span>
      <span v-else-if="disciple.injury_stacks > 0" class="tag hurt">
        伤 {{ disciple.injury_stacks }}
      </span>
    </div>
  </button>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
}

.card.selected {
  border-color: var(--accent);
  outline: 1px solid var(--accent);
}

.card.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.portrait {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 2 / 3;
  background: #ece9e1;
}

.portrait img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.initial {
  font-size: 32px;
  color: #b5afa2;
}

.meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 8px 10px;
  border-top: 1px solid var(--border);
}

.name {
  font-size: 14px;
}

.tag {
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--muted);
  font-size: 11px;
}

.tag.busy {
  border-color: var(--accent);
  color: var(--accent);
}

.tag.hurt {
  border-color: var(--danger);
  color: var(--danger);
}
</style>
