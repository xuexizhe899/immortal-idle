<script setup lang="ts">
import { computed } from 'vue'
import { discipleImage } from '../../presentation/assetPaths'
import { type DisplayCatalog } from '../../presentation/gameText'
import { useGameStore } from '../../stores/game'
import GameIcon from '../ui/GameIcon.vue'

defineProps<{ compact?: boolean; reorder?: boolean }>()
defineEmits<{ edit: []; prepare: [] }>()
const store = useGameStore()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const members = computed(() => store.party.map(id => store.disciples.find(d => d.id === id)).filter(d => !!d))
const limit = computed(() => catalog.value?.rules.max_party ?? 6)
</script>
<template>
  <div class="party-strip" :class="{ compact }">
    <div class="party-caption"><span class="eyebrow">出征同道</span><h3>出征阵容 <small>{{ members.length }} / {{ limit }}</small></h3><span class="muted">同道相携，问鼎云巅</span></div>
    <div class="party-slots">
      <div v-for="i in limit" :key="i" class="slot-wrap">
        <button class="party-slot" :aria-label="members[i - 1] ? `第${i}位 ${catalog?.disciples[members[i - 1]!.template_id]?.name ?? '弟子'}，调整阵容` : `第${i}位，添加出征弟子`" @click="$emit('edit')">
          <b class="slot-number">{{ i }}</b>
          <template v-if="members[i - 1]"><img :src="discipleImage(members[i - 1]!.template_id, catalog)" alt="" class="pixel-art" decoding="async" /><span>{{ catalog?.disciples[members[i - 1]!.template_id]?.name }}</span></template>
          <template v-else><GameIcon name="plus" /><span>待安排</span></template>
        </button>
        <div v-if="reorder && members[i - 1]" class="slot-moves">
          <button :disabled="store.busy || store.status !== 'idle' || i === 1" :aria-label="`${catalog?.disciples[members[i - 1]!.template_id]?.name}向前换位`" @click="store.moveParty(members[i - 1]!.id, -1)">前移</button>
          <button :disabled="store.busy || store.status !== 'idle' || i === members.length" :aria-label="`${catalog?.disciples[members[i - 1]!.template_id]?.name}向后换位`" @click="store.moveParty(members[i - 1]!.id, 1)">后移</button>
        </div>
      </div>
    </div>
    <div v-if="!compact" class="party-actions"><button class="btn btn-quiet" @click="$emit('edit')">{{ store.status === 'idle' ? '调整阵容' : '查看出征阵容' }}</button><button class="btn btn-primary" :disabled="store.busy" @click="$emit('prepare')"><GameIcon name="tower" />{{ store.status === 'idle' ? '前往问道塔' : ['cleared','defeated'].includes(store.status) ? '查看出征结算' : '继续出征' }}</button></div>
  </div>
</template>
<style scoped>
.party-strip{display:flex;align-items:center;gap:24px;padding:18px 26px;background:#f7f1e3f5;border:1px solid #c6ba98}.party-caption{min-width:150px}.party-caption h3{margin:2px 0;font-size:19px}.party-caption small{color:var(--gold);font:12px system-ui;margin-left:8px}.party-caption .eyebrow{font-size:8px}.party-slots{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;flex:1}.slot-wrap{min-width:0}.party-slot{position:relative;width:100%;height:86px;border:1px dashed #b1b69b;display:flex;align-items:center;justify-content:center;background:#e6e8d8;overflow:hidden;color:#8d9786;padding:0}.party-slot img{width:100%;height:100%;object-fit:contain;object-position:center bottom;padding:3px 2px 17px}.party-slot span{position:absolute;bottom:0;width:100%;padding:1px;font-size:10px;text-align:center;background:#f7f0dfdd;color:var(--ink)}.slot-number{position:absolute;top:2px;left:3px;z-index:1;font-size:9px;background:#f7f0dfdd;padding:0 3px;color:var(--jade)}.party-slot:has(img){border-style:solid;border-color:#9dba9c}.party-slot:hover{border-color:var(--jade)}.slot-moves{display:flex;gap:2px;margin-top:3px}.slot-moves button{flex:1;padding:2px 0;min-height:30px;border:1px solid #cec4a6;background:#eee7d3;font-size:9px;color:var(--jade)}.party-actions{display:flex;align-items:center;gap:10px}.compact{padding:0;border:0;background:none}.compact .party-caption{display:none}
@media(max-width:1000px){.party-strip{gap:12px;padding:16px}.party-actions{flex-direction:column;gap:5px}}
@media(max-width:640px){.party-strip{flex-wrap:wrap;padding:0;gap:12px}.party-caption{min-width:0}.party-caption h3{font-size:17px}.party-caption>.muted{display:none}.party-slots{width:100%;flex-basis:100%;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.party-slot{height:92px}.party-actions{margin-left:auto}.party-actions>.btn-quiet{display:none}.party-actions>.btn{min-height:40px;font-size:12px}.slot-moves button{min-height:36px;font-size:10px}}
</style>
