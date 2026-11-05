<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { components } from './generated/api'

type Health = components['schemas']['HealthResponse']

const health = ref<Health | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)

async function probe() {
  loading.value = true
  error.value = null
  try {
    const response = await fetch('/api/health')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    health.value = (await response.json()) as Health
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

onMounted(probe)
</script>

<template>
  <header class="head">
    <h1>修仙放置</h1>
    <p class="sub">单机多档 · 局外挂机 · 局内出征</p>
  </header>

  <section class="card">
    <div class="row">
      <span class="label">服务端</span>
      <span v-if="loading" class="state pending">检查中…</span>
      <span v-else-if="error" class="state bad">{{ error }}</span>
      <span v-else class="state good">已连通</span>
    </div>
    <div v-if="health" class="row">
      <span class="label">契约</span>
      <span class="mono">{{ health.service }} · v{{ health.version }}</span>
    </div>
    <div v-if="health" class="row">
      <span class="label">来源</span>
      <span class="mono">HealthResponse 由 OpenAPI 生成</span>
    </div>
    <button class="probe" type="button" :disabled="loading" @click="probe">重新探测</button>
  </section>

  <section class="card">
    <h2>下一步 · T01</h2>
    <ol class="steps">
      <li>配置 schema 与悬空引用校验</li>
      <li>存档模型、多档与 CAS</li>
      <li>惰性分段结算引擎</li>
    </ol>
  </section>
</template>

<style scoped>
.head {
  margin-bottom: 32px;
}

h1 {
  font-size: 28px;
  margin: 0 0 6px;
}

.sub {
  margin: 0;
  color: var(--muted);
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 22px 20px;
  margin-bottom: 16px;
}

.row {
  display: flex;
  gap: 16px;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-of-type {
  border-bottom: none;
}

.label {
  width: 64px;
  flex: none;
  color: var(--muted);
  font-size: 13px;
}

.state {
  font-size: 14px;
}

.good {
  color: var(--accent);
}

.bad {
  color: var(--danger);
}

.pending {
  color: var(--muted);
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
}

.probe {
  margin-top: 14px;
  padding: 7px 14px;
  font: inherit;
  font-size: 14px;
  color: var(--text);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
}

.probe:hover:not(:disabled) {
  border-color: var(--muted);
}

.probe:disabled {
  color: var(--muted);
  cursor: default;
}

h2 {
  font-size: 16px;
  margin: 0 0 10px;
}

.steps {
  margin: 0;
  padding-left: 20px;
  color: var(--muted);
}

.steps li {
  padding: 2px 0;
}
</style>
