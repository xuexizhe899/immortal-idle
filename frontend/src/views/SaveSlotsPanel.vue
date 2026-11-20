<script setup lang="ts">
import { onMounted,ref } from 'vue'
import { api } from '../api/client'
import { useGameStore } from '../stores/game'
const store=useGameStore();const newName=ref('');const importText=ref('');const localError=ref('');const message=ref('');const deleteId=ref<number|null>(null);const exportBusy=ref(false)
onMounted(()=>{void store.loadSaves()})
function date(value:string){return new Date(value).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}
async function create(){if(!newName.value.trim())return;await store.createSave(newName.value.trim());if(!store.error)newName.value=''}
async function remove(id:number){await store.deleteSave(id);if(!store.error)deleteId.value=null}
async function exportOne(id:number){localError.value='';exportBusy.value=true;try{const data=await api.exportSave(id);const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download=`宗门存档-${id}.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message.value='存档已导出，请保管好备份文件。'}catch(error){localError.value=error instanceof Error?error.message:'导出失败，请重试'}finally{exportBusy.value=false}}
async function importOne(){localError.value='';try{const payload:unknown=JSON.parse(importText.value);await store.importSave(payload);if(!store.error){importText.value='';message.value='存档已导入，并切换至新存档。'}}catch{localError.value='存档内容无法解析，请确认粘贴了完整的 JSON 文件。'}}
async function readFile(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;try{importText.value=await file.text();localError.value=''}catch{localError.value='无法读取文件，请重试'}input.value=''}
</script>
<template>
  <div class="saves-panel">
    <div class="save-summary"><span class="save-seal" aria-hidden="true">存</span><div><h3>各守一方山门</h3><p class="muted">各存档独立经营，切换时会结算该档离线收益。</p></div><span class="save-count">{{ store.saves.length }} 个宗门</span></div>
    <div v-if="localError" class="error-box" role="alert">{{ localError }}</div>
    <div v-if="message" class="notice-box" role="status">{{ message }}</div>
    <div class="save-tools">
      <details class="new-save"><summary>新立宗门<span>另起一段修行</span></summary><form class="create-save" @submit.prevent="create"><label class="field-label" for="new-save-name">新立宗门</label><div><input id="new-save-name" v-model="newName" maxlength="60" placeholder="为新存档取一个名字" /><button class="btn btn-primary" :disabled="store.busy||!newName.trim()">新建存档</button></div></form></details>
      <details class="import-save"><summary>从备份导入<span>延续已有山门</span></summary><div><label class="field-label" for="save-file">选择存档文件</label><input id="save-file" type="file" accept=".json,application/json" @change="readFile" /><label class="field-label" for="import-save-text">或粘贴存档内容</label><textarea id="import-save-text" v-model="importText" rows="4" placeholder="粘贴导出的完整 JSON 内容"></textarea><p class="muted">导入会建立新存档，保留现有宗门。</p><button class="btn" :disabled="store.busy||!importText.trim()" @click="importOne">导入并进入</button></div></details>
    </div>
    <div class="save-list" tabindex="0" aria-label="已有宗门存档">
      <article v-for="save in store.saves" :key="save.slot_id" class="save-row" :class="{active:save.slot_id===store.slotId}">
        <span class="save-mark" aria-hidden="true">{{ save.slot_id===store.slotId?'印':'宗' }}</span>
        <div class="save-name"><strong>{{ save.name }}</strong><span v-if="save.slot_id===store.slotId" class="badge">当前宗门</span><small>最近打理 · {{ date(save.updated_at) }}</small></div>
        <div class="save-actions"><button class="btn btn-small" :disabled="store.busy||save.slot_id===store.slotId" @click="store.switchSave(save.slot_id)">{{ save.slot_id===store.slotId?'当前':'进入' }}</button><button class="btn btn-small" :disabled="store.busy" @click="store.duplicateSave(save.slot_id,`${save.name} 副本`)">复制</button><button class="btn btn-small" :disabled="store.busy||exportBusy" @click="exportOne(save.slot_id)">导出</button><button class="btn btn-small btn-quiet delete-button" :disabled="store.busy" @click="deleteId=save.slot_id">删除</button></div>
        <div v-if="deleteId===save.slot_id" class="delete-confirm" role="alert"><p>确认删除「{{ save.name }}」？删除后无法恢复，建议先导出备份。</p><div><button class="btn btn-small" @click="deleteId=null">保留存档</button><button class="btn btn-small btn-danger" :disabled="store.busy" @click="remove(save.slot_id)">确认删除</button></div></div>
      </article>
      <p v-if="!store.saves.length&&store.busy" class="notice-box" role="status">正在查阅宗门存档……</p>
      <div v-else-if="!store.saves.length" class="save-empty"><strong>尚无宗门存档</strong><p>展开上方“新立宗门”，为第一座山门取名；已有备份时，可选择“从备份导入”。</p></div>
    </div>
  </div>
</template>
<style scoped>
.saves-panel { min-width: 0; }
.save-summary { display: flex; align-items: center; gap: 13px; padding: 6px 0 16px; border-bottom: 1px solid var(--border); }
.save-summary > div { flex: 1; min-width: 0; }
.save-seal { display: grid; place-items: center; flex: none; width: 47px; height: 54px; font: 29px var(--font-display); color: var(--gold); border: 1px solid #8b7042; background: #293d35; box-shadow: inset 0 0 0 4px var(--surface), inset 0 0 0 5px #6f5a37; }
.save-summary h3 { margin: 0 0 6px; color: var(--ink); font-size: 22px; }
.save-summary p { margin: 0; font-size: 11px; line-height: 1.8; }
.save-count { flex: none; color: var(--gold); font-size: 11px; font-variant-numeric: tabular-nums; }
.save-tools { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 9px; margin: 14px 0; }
.save-tools > details { padding: 13px; border: 1px solid var(--border); border-left: 3px solid var(--jade-deep); background: var(--surface); }
.save-tools > details[open] { grid-column: 1 / -1; }
.save-tools summary { min-height: 27px; color: var(--jade); font: 16px var(--font-display); line-height: 1.8; }
.save-tools summary > span { display: block; margin: 4px 0 0 18px; color: var(--muted); font: 10px 'Microsoft YaHei', sans-serif; }
.save-tools > details[open] > summary > span { display: none; }
.create-save { padding-top: 16px; }
.create-save > div { display: flex; gap: 9px; }
.create-save > div > input { flex: 1; min-width: 0; }
.import-save > div { padding-top: 16px; }
.import-save input { width: 100%; margin-bottom: 16px; font-size: 11px; }
.import-save textarea { background: var(--surface-raised); font-family: monospace; font-size: 11px; }
.import-save .muted { margin: 8px 0 12px; }
.save-list { max-height: min(56dvh, 560px); margin: 15px 0; padding: 1px; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.save-list:focus-visible { outline: 2px solid var(--jade); outline-offset: 2px; }
.save-row { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 15px 13px; margin-bottom: 7px; border: 1px solid var(--border); border-left: 3px solid #527463; background: var(--surface); }
.save-row.active { border-color: #66977b; border-left-color: var(--jade); background: #1d3933; }
.save-mark { display: grid; place-items: center; flex: none; width: 35px; height: 39px; border: 1px solid #4d6c60; color: var(--muted); background: var(--surface-inset); font: 22px var(--font-display); }
.save-row.active > .save-mark { border-color: var(--jade); color: #0b1b16; background: var(--jade); }
.save-name { flex: 1; min-width: 130px; }
.save-name strong { display: inline-block; max-width: 100%; overflow-wrap: anywhere; color: var(--ink); font: 17px var(--font-display); line-height: 1.6; }
.save-name > .badge { color: var(--jade); border-color: #4c856c; background: var(--jade-light); }
.save-name small { display: block; margin-top: 6px; color: var(--muted); font-size: 10px; line-height: 1.8; font-variant-numeric: tabular-nums; }
.save-actions { display: flex; gap: 5px; }
.save-actions .btn { min-height: 38px; }
.delete-button { color: var(--danger); }
.delete-confirm { width: 100%; padding: 12px; border: 1px solid #865247; background: #3b2824; }
.delete-confirm p { margin: 0 0 10px; font-size: 12px; }
.delete-confirm > div { display: flex; gap: 8px; }
.save-empty { padding: 21px 15px; border: 1px dashed var(--border); background: var(--surface-inset); }
.save-empty strong { color: var(--jade); font: 21px var(--font-display); }
.save-empty p { max-width: 40em; margin: 10px 0 0; color: var(--muted); font-size: 12px; line-height: 1.9; }
.saves-panel button:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
@media (max-width: 640px) {
  .save-summary { gap: 10px; align-items: flex-start; }
  .save-seal { width: 39px; height: 47px; font-size: 25px; }
  .save-summary h3 { font-size: 20px; }
  .save-summary p, .save-count { font-size: 10px; }
  .save-count { margin-top: 4px; white-space: nowrap; }
  .save-tools { gap: 7px; }
  .save-tools > details { padding: 10px; }
  .save-tools summary { min-height: 40px; font-size: 15px; }
  .save-row { gap: 10px; padding: 12px 10px; }
  .save-mark { width: 32px; height: 37px; }
  .save-name { min-width: 110px; }
  .save-name strong { margin-right: 6px; font-size: 17px; }
  .save-name small { font-size: 11px; }
  .save-actions { width: 100%; gap: 5px; }
  .save-actions .btn { flex: 1; min-height: 44px; padding-inline: 6px; font-size: 11px; }
  .create-save > div { flex-direction: column; }
  .save-tools > details[open] { grid-column: 1 / -1; }
  .save-tools input, .save-tools > .new-save .btn, .import-save .btn, .delete-confirm .btn { min-height: 44px; }
  .delete-confirm > div { flex-wrap: wrap; }
}
</style>
