<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import { useGameStore } from '../stores/game'

const store = useGameStore()
const newName = ref('')
const importText = ref('')

onMounted(() => {
  void store.loadSaves()
})

async function create() {
  const name = newName.value.trim()
  if (!name) return
  await store.createSave(name)
  newName.value = ''
}

async function duplicate(id: number, name: string) {
  await store.duplicateSave(id, `${name} 副本`)
}

async function remove(id: number) {
  await store.deleteSave(id)
}

async function exportOne(id: number) {
  const data = await api.exportSave(id)
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `save-${id}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

async function importOne() {
  const text = importText.value.trim()
  if (!text) return
  const payload = JSON.parse(text)
  await store.importSave(payload)
  importText.value = ''
}
</script>

<template>
  <div class="slots-panel">
    <div class="panel-head">
      <h2>多档管理</h2>
      <span class="hint">当前 #{{ store.slotId }}</span>
    </div>

    <div class="list">
      <div
        v-for="save in store.saves"
        :key="save.slot_id"
        class="row"
        :class="{ active: save.slot_id === store.slotId }"
      >
        <span class="name">#{{ save.slot_id }} {{ save.name }}</span>
        <span class="hint">rev {{ save.revision }}</span>
        <button class="mini" type="button" @click="store.switchSave(save.slot_id)">切换</button>
        <button class="mini" type="button" @click="duplicate(save.slot_id, save.name)">复制</button>
        <button class="mini" type="button" @click="exportOne(save.slot_id)">导出</button>
        <button class="mini danger" type="button" @click="remove(save.slot_id)">删除</button>
      </div>
    </div>

    <div class="create-line">
      <input v-model="newName" class="input" placeholder="新存档名" />
      <button class="mini" type="button" @click="create">新建</button>
    </div>

    <div class="import-line">
      <textarea v-model="importText" class="textarea" rows="3" placeholder="粘贴导出的 JSON"></textarea>
      <button class="mini" type="button" @click="importOne">导入</button>
    </div>
  </div>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.hint {
  color: var(--muted);
  font-size: 12px;
}

.list {
  display: flex;
  flex-direction: column;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.row.active .name {
  color: var(--accent);
}

.name {
  flex: 1;
  font-size: 14px;
}

.mini {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.mini:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.mini.danger:hover {
  border-color: var(--danger);
  color: var(--danger);
}

.create-line {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  font-size: 13px;
}

.import-line {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  font-size: 12px;
  resize: vertical;
}
</style>
