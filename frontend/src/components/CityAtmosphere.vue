<script setup lang="ts">
const stars = [[7, 5], [17, 11], [29, 4], [42, 8], [57, 3], [68, 11], [79, 5], [91, 13], [95, 37], [6, 46]]
const lanterns = [[21, 26], [50, 24], [79, 25], [20, 51], [74, 55], [36, 72], [61, 73]]
</script>

<template>
  <div class="city-atmosphere" aria-hidden="true">
    <div class="night-tint"></div><div class="night-sky"></div><div class="warm-tint"></div>
    <div class="stars"><i v-for="([x,y],i) in stars" :key="i" :style="{left:`${x}%`,top:`${y}%`,animationDelay:`${i*.7}s`}"></i><span class="moon"></span></div>
    <div class="lanterns"><i v-for="([x,y],i) in lanterns" :key="i" :style="{left:`${x}%`,top:`${y}%`}"></i></div>
    <div class="cloud cloud-front"></div><div class="cloud cloud-back"></div>
  </div>
</template>

<style scoped>
.city-atmosphere{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:1;mask-image:linear-gradient(transparent,#000 5%,#000 94%,transparent)}
.night-tint,.warm-tint{position:absolute;inset:0;transition:opacity 3s ease}.night-tint{background:#183561;mix-blend-mode:color;opacity:var(--night-opacity)}.warm-tint{background:linear-gradient(135deg,#ffba65,#c76c58 70%,transparent);mix-blend-mode:soft-light;opacity:var(--warm-opacity)}
.night-sky{position:absolute;inset:0;background:linear-gradient(#15294a 0%,#1c33577a 15%,transparent 38%);opacity:var(--night-opacity);transition:opacity 3s ease}
.stars,.lanterns{position:absolute;inset:0;transition:opacity 3s ease}.stars{opacity:var(--night-opacity)}.stars>i{position:absolute;width:2px;height:2px;background:#fff5cd;box-shadow:0 0 5px #faf5dc;animation:twinkle 5s ease-in-out infinite alternate}.moon{position:absolute;right:8%;top:5%;width:25px;height:25px;border-radius:50%;background:#f7edce;box-shadow:0 0 22px 9px #e5eaca24}
.lanterns{opacity:var(--lantern-opacity)}.lanterns>i{position:absolute;width:5px;height:6px;background:#ffe0a0;box-shadow:0 0 10px 5px #f2b94a88,0 0 24px 12px #ffd07c20;transform:translate(-50%,-50%)}
.cloud{position:absolute;width:70%;height:20%;bottom:0;opacity:.15;background:radial-gradient(ellipse at 50% 80%,#eef6f2 0,transparent 68%);filter:blur(7px);animation:cloud-drift 50s linear infinite alternate}.cloud-front{left:-15%;bottom:1%}.cloud-back{right:-20%;bottom:17%;opacity:.08;animation-duration:65s;animation-direction:alternate-reverse}
@keyframes cloud-drift{to{transform:translateX(15%)}}@keyframes twinkle{to{opacity:.35}}
</style>
