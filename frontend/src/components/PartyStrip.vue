<script setup lang="ts">
import { computed } from 'vue'
import GameIcon from './GameIcon.vue'
import { imageOf, type DisplayCatalog } from './gameDisplay'
import { useGameStore } from '../stores/game'
defineProps<{ compact?: boolean }>()
defineEmits<{ edit: []; prepare: [] }>()
const store = useGameStore()
const catalog = computed(() => store.catalog as DisplayCatalog | null)
const members = computed(() => store.party.map(id => store.disciples.find(d => d.id === id)).filter(d => !!d))
</script>
<template>
  <div class="party-strip" :class="{ compact }">
    <div class="party-caption"><span class="eyebrow">EXPEDITION PARTY</span><h3>出征阵容 <small>{{ members.length }} / 5</small></h3><span class="muted">同道相携，问鼎云巅</span></div>
    <div class="party-slots"><button v-for="i in 5" :key="i" class="party-slot" :aria-label="members[i - 1] ? `调整${catalog?.disciples[members[i - 1]!.template_id]?.name ?? '弟子'}` : '添加出征弟子'" @click="$emit('edit')"><template v-if="members[i - 1]"><img :src="imageOf(members[i - 1]!.template_id, catalog)" alt="" class="pixel-art" /><span>{{ catalog?.disciples[members[i - 1]!.template_id]?.name }}</span></template><template v-else><GameIcon name="plus" /><span>待安排</span></template></button></div>
    <div v-if="!compact" class="party-actions"><button class="btn btn-quiet" @click="$emit('edit')">{{ store.status === 'idle' ? '调整阵容' : '查看出征阵容' }}</button><button class="btn btn-primary" :disabled="store.busy" @click="$emit('prepare')"><GameIcon name="tower" />{{ store.status === 'idle' ? '前往问道塔' : ['cleared','defeated'].includes(store.status) ? '查看出征结算' : '继续出征' }}</button></div>
  </div>
</template>
<style scoped>
.party-strip { display:flex;align-items:center;gap:24px;padding:18px 26px;background:#f7f1e3f5;border:1px solid #c6ba98;box-shadow:0 5px 25px #27382d13 }.party-caption{min-width:170px}.party-caption h3{margin:2px 0;font-size:19px}.party-caption small{color:var(--gold);font:12px system-ui;margin-left:8px}.party-caption .eyebrow{font-size:8px}.party-slots{display:flex;gap:8px;flex:1;justify-content:center}.party-slot{position:relative;width:67px;height:76px;border:1px dashed #b1b69b;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#e6e8d8;overflow:hidden;color:#8d9786}.party-slot img{width:100%;height:100%;object-fit:cover;object-position:center 23%}.party-slot span{position:absolute;bottom:0;width:100%;padding:1px;font-size:10px;text-align:center;background:#f7f0dfdd;color:var(--ink)}.party-slot:has(img){border-style:solid;border-color:#9dba9c}.party-slot:hover{border-color:var(--jade)}.party-actions{display:flex;align-items:center;gap:10px}.compact{padding:0;border:0;box-shadow:none;background:none}.compact .party-caption{display:none}.compact .party-slot{width:80px;height:95px}
@media(max-width:1000px){.party-caption{min-width:140px}.party-strip{gap:12px;padding:16px}.party-actions{flex-direction:column;gap:5px}.party-slot{width:58px}}
@media(max-width:640px){.party-strip{flex-wrap:wrap;padding:14px;gap:12px}.party-caption{min-width:0}.party-caption h3{font-size:17px}.party-caption>.muted{display:none}.party-slots{width:100%;order:2;justify-content:space-between}.party-slot{width:calc((100vw - 80px) / 5);max-width:72px;height:75px}.party-actions{margin-left:auto}.party-actions>.btn-quiet{display:none}.party-actions>.btn{min-height:40px;font-size:12px}.compact .party-slots{order:0}.compact .party-slot{width:16%;height:80px}.compact{padding:0}}
</style>
