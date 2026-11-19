<script setup lang="ts">
import { number } from '../../shared/format'
import { statNames, type DisplaySkill } from '../../presentation/gameText'
defineProps<{ skill: DisplaySkill; passive?: boolean }>()
const targets: Record<string,string> = { enemy_first:'首位敌人', enemy_lowest:'气血比例最低的敌人', all_enemies:'敌方', ally_lowest:'气血比例最低的同道', all_allies:'我方', self:'自身', ally_template:'指定同道' }
const conditions: Record<string,string> = { always:'常驻生效', shielded:'自身有护盾时生效', target_weakened:'目标已被降防时生效', first_round:'首轮行动时生效' }
const bonuses: Record<string,string> = { damage:'伤害', healing:'治疗效果', shielding:'护盾效果', atk:'攻击', def:'防御', hp:'气血上限', spd:'身法' }
</script>
<template>
  <article class="skill-detail" :class="{ passive, 'skill-pending': !skill.implemented }">
    <header><span class="skill-seal" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><template v-if="passive"><path d="M16 5v22M5 16h22M8 8l16 16M8 24 24 8" /><path d="m16 8 8 8-8 8-8-8Z" /></template><template v-else><path d="m21 5 6 1-1 6-13 13-6-6L21 5Z" /><path d="m6 16 10 10M5 27l5-5M20 9l3 3" /></template></svg></span><div class="skill-name"><strong>{{ skill.name }}</strong><small>{{ passive ? '天赋被动' : '主动招式' }}</small></div><span class="badge" :class="{ 'badge-muted': !skill.implemented }">{{ skill.implemented ? '已生效' : '待开放' }}</span></header>
    <p>{{ skill.description }}</p>
    <template v-if="skill.implemented">
      <div class="skill-facts"><span v-if="!passive">每场初次就绪 · 每隔 {{ skill.cooldown }} 次自身行动施展</span><span v-else>{{ conditions[skill.condition] ?? skill.condition }}</span></div>
      <ul v-if="skill.actions.length"><li v-for="(action,index) in skill.actions" :key="index"><template v-if="action.kind === 'damage'">对{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}造成 {{ number(action.coefficient * 100) }}% 攻击的伤害</template><template v-else-if="action.kind === 'heal'">为{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}恢复 {{ number(action.coefficient * 100) }}% 攻击的气血</template><template v-else-if="action.kind === 'shield'">为{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}施加 {{ number(action.coefficient * 100) }}% 攻击的护盾 · {{ action.duration }} 轮</template><template v-else>{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}{{ statNames[action.stat] ?? action.stat }} {{ action.value >= 0 ? '+' : '' }}{{ number(action.value * 100) }}% · {{ action.duration }} 轮</template></li></ul>
      <div class="skill-bonuses"><span v-for="(value,key) in skill.bonuses" :key="key">{{ bonuses[key] ?? key }} {{ value >= 0 ? '+' : '' }}{{ number(value * 100) }}%</span></div>
    </template>
  </article>
</template>
<style scoped>
.skill-detail{padding:14px 0;border-bottom:1px solid #d3c8aa}.skill-detail header{display:flex;align-items:center;gap:10px}.skill-seal{display:grid;place-items:center;width:39px;height:43px;flex:none;border:1px solid #8fa58a;background:#dfe8cf;color:#326c55;clip-path:polygon(0 0,100% 0,100% 85%,50% 100%,0 85%)}.skill-seal svg{width:26px;height:26px;stroke:currentColor;stroke-width:1.5;stroke-linecap:square;stroke-linejoin:miter}.passive .skill-seal{background:#ebe2c6;border-color:#c3ae7d;color:#8c6844}.skill-name{min-width:0}.skill-detail strong{display:block;font:17px 'SimSun',serif;color:#213f36;overflow-wrap:anywhere}.skill-detail small{font-size:10px;color:#8c6844}.skill-detail .badge{font-size:10px;margin-left:auto;flex:none}.skill-detail p{font-size:12px;color:var(--muted);margin:10px 0;line-height:1.9}.skill-facts{padding:7px 9px;border-left:2px solid #8fa58a;background:#e5ead8;font-size:11px;line-height:1.7;color:#326c55}.skill-detail ul{padding-left:18px;margin:9px 0;font-size:12px;color:#536c50;line-height:1.8}.skill-detail li{margin:5px 0;padding-left:2px}.skill-detail li::marker{color:#a68a50}.skill-bonuses{display:flex;gap:6px;flex-wrap:wrap;font-size:11px;color:var(--jade)}.skill-bonuses>span{padding:3px 7px;border:1px solid #c5cfb3;background:#edf0df;font-variant-numeric:tabular-nums}.skill-pending .skill-seal{background:#e7e4d7;border-color:#c3bfaa;color:#878b75}
</style>
