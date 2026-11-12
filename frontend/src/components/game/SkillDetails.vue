<script setup lang="ts">
import { number } from '../../shared/format'
import { statNames, type DisplaySkill } from '../../presentation/gameText'
defineProps<{ skill: DisplaySkill; passive?: boolean }>()
const targets: Record<string,string> = { enemy_first:'首位敌人', enemy_lowest:'气血比例最低的敌人', all_enemies:'敌方', ally_lowest:'气血比例最低的同道', all_allies:'我方', self:'自身', ally_template:'指定同道' }
const conditions: Record<string,string> = { always:'常驻生效', shielded:'自身有护盾时生效', target_weakened:'目标已被降防时生效', first_round:'首轮行动时生效' }
const bonuses: Record<string,string> = { damage:'伤害', healing:'治疗效果', shielding:'护盾效果', atk:'攻击', def:'防御', hp:'气血上限', spd:'身法' }
</script>
<template>
  <article class="skill-detail">
    <header><strong>{{ skill.name }}</strong><small>{{ passive ? '天赋被动' : '主动招式' }}</small><span class="badge" :class="{ 'badge-muted': !skill.implemented }">{{ skill.implemented ? '已生效' : '待开放' }}</span></header>
    <p>{{ skill.description }}</p>
    <template v-if="skill.implemented">
      <div class="skill-facts"><span v-if="!passive">每场初次就绪 · 每隔 {{ skill.cooldown }} 次自身行动施展</span><span v-else>{{ conditions[skill.condition] ?? skill.condition }}</span></div>
      <ul v-if="skill.actions.length"><li v-for="(action,index) in skill.actions" :key="index"><template v-if="action.kind === 'damage'">对{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}造成 {{ number(action.coefficient * 100) }}% 攻击的伤害</template><template v-else-if="action.kind === 'heal'">为{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}恢复 {{ number(action.coefficient * 100) }}% 攻击的气血</template><template v-else-if="action.kind === 'shield'">为{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}施加 {{ number(action.coefficient * 100) }}% 攻击的护盾 · {{ action.duration }} 轮</template><template v-else>{{ targets[action.target] }}{{ action.count > 1 ? `至多${action.count}人` : '' }}{{ statNames[action.stat] ?? action.stat }} {{ action.value >= 0 ? '+' : '' }}{{ number(action.value * 100) }}% · {{ action.duration }} 轮</template></li></ul>
      <div class="skill-bonuses"><span v-for="(value,key) in skill.bonuses" :key="key">{{ bonuses[key] ?? key }} {{ value >= 0 ? '+' : '' }}{{ number(value * 100) }}%</span></div>
    </template>
  </article>
</template>
<style scoped>
.skill-detail{padding:10px 0;border-bottom:1px solid #d3c8aa}.skill-detail header{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.skill-detail strong{font-size:13px}.skill-detail small{font-size:9px;color:var(--gold)}.skill-detail .badge{font-size:8px;margin-left:auto}.skill-detail p{font-size:11px;color:var(--muted);margin:6px 0}.skill-facts{font-size:10px;color:#5e7756}.skill-detail ul{padding-left:15px;margin:5px 0;font-size:10px;color:#657459}.skill-detail li{margin:4px 0}.skill-bonuses{display:flex;gap:7px;flex-wrap:wrap;font-size:10px;color:var(--jade)}
</style>
