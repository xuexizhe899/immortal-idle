<script setup lang="ts">
import type { DiscipleState } from '../../api/client'
import { discipleImage } from '../../presentation/assetPaths'
import { leanNames, rarityNames } from '../../presentation/gameText'
defineProps<{ disciple: DiscipleState; name: string; selected: boolean; disabled?: boolean; active?: boolean; asset?: string; lean?: string; rarity?: number; duty?: boolean }>()
defineEmits<{ toggle: [] }>()
</script>
<template>
  <button class="disciple-card" :class="{ selected, active }" :disabled="disabled" @click="$emit('toggle')">
    <div class="portrait">
      <span class="portrait-ring" aria-hidden="true"></span>
      <img :src="asset ?? discipleImage(disciple.template_id)" :alt="name" class="pixel-art" loading="lazy" decoding="async" />
      <span v-if="lean" class="lean-seal">{{ leanNames[lean] }}</span>
      <span v-if="selected" class="selected-mark"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8 3 3 7-7" /></svg>已入队</span>
      <span class="level-mark">{{ disciple.level }}<small>级</small></span>
    </div>
    <div class="card-meta">
      <strong>{{ name }}</strong>
      <small class="rarity-label">{{ rarityNames[rarity ?? 1] }}</small>
      <span v-if="disciple.busy" class="card-status occupied">出征中</span>
      <span v-else-if="duty" class="card-status occupied">值守中</span>
      <span v-else-if="disciple.injury_stacks" class="card-status hurt">伤势 {{ disciple.injury_stacks }} 层</span>
      <span v-else class="card-status">境界 {{ disciple.realm }}</span>
    </div>
  </button>
</template>
<style scoped>
.disciple-card{position:relative;padding:4px;border:1px solid #b7b99b;border-radius:3px;background:#f6f1df;text-align:left;overflow:hidden;box-shadow:0 2px 0 #8c68441a;transition:border-color .16s,background-color .16s}
.disciple-card:hover,.disciple-card.active{border-color:#326c55;background:#eaf0de}.disciple-card.selected{border-color:#326c55}.disciple-card:focus-visible{outline:2px solid var(--jade);outline-offset:3px}.disciple-card:disabled{cursor:default}
.portrait{position:relative;aspect-ratio:1 / 1.1;background:#dfe8cf;overflow:hidden;border:1px solid #c4c9ac}
.portrait::before,.portrait::after{content:'';position:absolute;z-index:1;pointer-events:none;width:15px;height:15px;border-color:#8c6844;border-style:solid;opacity:.6}.portrait::before{top:4px;right:4px;border-width:1px 1px 0 0}.portrait::after{bottom:4px;left:4px;border-width:0 0 1px 1px}
.portrait-ring{position:absolute;width:78%;aspect-ratio:1;border:1px solid #a4b99c;border-radius:50%;left:11%;top:18%;box-shadow:0 0 0 7px #d2dec1}.portrait img{position:relative;display:block;width:100%;height:100%;object-fit:cover;object-position:center 15%}
.lean-seal{position:absolute;top:7px;left:7px;min-width:24px;padding:4px 3px;color:#326c55;border:1px solid #8da686;background:#f6f1dfee;text-align:center;font:13px 'SimSun',serif;box-shadow:2px 2px 0 #326c5510}
.selected-mark{position:absolute;bottom:7px;left:7px;display:flex;align-items:center;gap:3px;padding:3px 5px;background:#326c55;color:#fff8df;font-size:10px;line-height:1.3}.selected-mark svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2}
.level-mark{position:absolute;right:7px;bottom:5px;color:#213f36;font-size:19px;font-weight:600;font-variant-numeric:tabular-nums;text-shadow:0 1px 2px #f6f1df,0 0 5px #f6f1df}.level-mark small{font-size:10px;margin-left:2px;font-weight:400}
.card-meta{position:relative;padding:9px 6px 6px}.card-meta strong{display:block;font:17px 'SimSun',serif;color:#213f36;line-height:1.4;overflow-wrap:anywhere}.rarity-label{display:block;font-size:10px;color:#8c6844;margin-top:2px}.card-status{display:flex;align-items:center;gap:5px;font-size:11px;color:#326c55;margin-top:7px;padding-top:6px;border-top:1px solid #d9d5bc}.card-status::before{content:'';width:5px;height:5px;background:currentColor;transform:rotate(45deg);flex:none}.card-status.occupied{color:#8c6844}.card-status.hurt{color:var(--danger)}
@media(max-width:640px){.disciple-card{padding:3px}.card-meta{padding:7px 4px 5px}.card-meta strong{font-size:15px}.card-status{font-size:10px;gap:4px}.selected-mark{font-size:9px;left:4px;bottom:5px;padding:3px}.level-mark{font-size:16px;right:5px}.lean-seal{top:5px;left:5px;min-width:22px;font-size:12px}}
@media(prefers-reduced-motion:reduce){.disciple-card{transition:none}}
</style>
