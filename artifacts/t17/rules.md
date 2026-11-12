# T17 · 战斗规则账本

记录日期：2026-11-12（北京时间）。适用版本：T16 六人自动战斗与当前配置。
本账本只描述可定位的当前事实，不代表平衡结论；数值目标见 [balance-report.md](balance-report.md)。

> 后续变更：T18 已实施境界 1/2/3 等级上限 3/6/10、突破费用 0.5×/0.75×、招募只负责首次获得；本账本以下记录 T17 当时规则，培养入口与费用以 [T18 规则方案](../t18/progression-rules.md) 为准。

主要来源：

- `backend/app/domain/battle.py`：回合、目标、伤害、治疗、护盾、状态、羁绊修正。
- `backend/app/domain/run_engine.py`：出发快照、节点、词条、跨层气血、失败与结算。
- `backend/app/domain/progression.py`、`recruit.py`、`craft.py`、`duty.py`、`settle.py`、`injuries.py`。
- `backend/app/models/battle.py`、`models/save.py`。
- `config/disciples/`、`skills/`、`bonds/`、`affixes/`、`enemies/`、`modes/tower.json`。

## 1. 属性、成长与伤害次序

| 项目 | 当前实现 | 来源 | 已知限制 / 建议目标 |
|---|---|---|---|
| 基础属性 | 使用弟子模板 `base_stats` 的 `hp/atk/def/spd` | `config/disciples/*.json`、`run_engine.combatant` | 不同品质只通过基础值和技能差异体现，没有额外品质乘区 |
| 等级成长 | 每级 `+10%`，只作用于 `atk/def/hp` | `progression.LEVEL_GROWTH=0.10`、`combatant` | **速度不随等级/境界成长**；T18 需要决定是否保留 |
| 境界成长 | 每阶 `+5%`，只作用于 `atk/def/hp` | `progression.REALM_GROWTH=0.05` | 同上；境界目前主要来自重复招募或破境丹 |
| 伤势折扣 | 每层攻击 `-10%`，最多 3 层，最低 `0.7` 倍攻击 | `injuries.attack_multiplier` | 只影响攻击，不影响防御、气血、速度；战斗中不自然消退 |
| 宗门永久加成 | `state.bonuses` 在出发时加到 `atk/def/hp/spd`，加区百分比 | `run_engine.combatant`、`domain/craft.py` | 所有弟子共享；不是个人装备。T19 若改为个人物品需单独迁移 |
| 局内词条 | 按 `run` 作用域的加区百分比加到固定参战属性 | `run_engine.with_affixes`、`config/affixes` | 选词条时按气血比例重算当前气血并向下取整 |
| 自身常驻被动 | `condition="always"` 的 `bonuses` 在出发时计入属性 | `run_engine.combatant` | 条件被动不进入固定属性，只在本次行动结算时加成 |
| 临时属性增减 | `buff` 状态按来源和属性覆盖；不同来源相加；总加成限制在 `-50%..+100%`，属性最低为 1 | `battle.Unit.stat`、`apply_effect` | 只影响战斗内属性，不写回永久层 |
| 最终伤害 | `max(1, floor(攻击 × 技能系数 × (1+条件伤害加成) × 100 / (100+目标防御)))` | `battle.apply_effect` | 没有暴击、闪避、穿透、持续伤害；最低 1 点 |
| 治疗 | `min(目标最大气血−当前气血, floor(攻击 × 系数 × (1+治疗加成)))` | `battle.apply_effect` | **战报不记录未生效的溢出量**，只能统计有效治疗 |
| 护盾 | `floor(攻击 × 系数 × (1+护盾加成))`；同来源取较大值，新来源只填剩余容量，总护盾不超过目标最大气血 | `battle.has_effect`、`apply_effect` | 护盾持续到 `R+D` 轮开始；战报记录实际增加量 |
| 取整位置 | 伤害、治疗、护盾在效果结算时向下取整；气血上限在出发/词条时向下取整 | `battle.py`、`run_engine.combatant` | 多次小加成不会在每一步重新取整 |

## 2. 行动、目标与终止

| 项目 | 当前实现 | 来源 | 已知限制 / 建议目标 |
|---|---|---|---|
| 队伍规模 | 双方 1–6 人；普通/精英/首领当前各 3 名敌人 | `run_engine.MAX_PARTY=6`、`tower.encounters` | 六人是上限，不要求满编 |
| 每轮行动 | 每名存活单位每轮一次主行动；主动可用则施放，否则普攻 | `battle.simulate_battle` | 主动无有效目标时改普攻，且不消耗冷却 |
| 出手顺序 | 每轮开始按 `身法降序 → 我方优先 → 槽位升序` 排序 | `battle.simulate_battle` | 身法变化从下一轮生效；当轮中途不重排 |
| 目标枚举 | 首个存活敌人、最低气血比例敌人、最低气血比例友方、自身、全体、按模板的友方 | `battle.targets_for` | 并列按槽位；目标在行动开始时固化，已倒下目标跳过，不自动改打 |
| 冷却 | 首次行动即可用；使用后 `next_active = 当前行动次数 + cooldown`；冷却 3 即第 1、4、7 次自身行动 | `battle.simulate_battle` | 冷却按自身行动计数，不按现实时间或全局轮次 |
| 状态到期 | 第 R 轮施加、持续 D 轮，在第 R+D 轮开始清除 | `battle.simulate_battle` 轮首过滤 | 护盾、增减益同规则；同来源刷新不叠加 |
| 护盾吸收 | 伤害先扣护盾，再扣气血；按状态列表顺序消耗 | `battle.apply_effect` | 文档要求“同顺序按稳定 ID”，当前实现按施加列表顺序；同来源刷新会把状态移到列表末尾，存在次序差异，建议在 T20 前复核 |
| 治疗/护盾溢出 | 治疗不超过缺失气血；护盾不超过最大气血 | `battle.apply_effect` | 治疗溢出未写入战报；护盾实际增加量会记录 |
| 回合上限 | 最多 20 轮；双方仍存活则 `reason="round_limit"`，按失败结算 | `battle.ROUND_LIMIT=20`、`run_status` | 不伪造气血清零；战报保留真实剩余气血 |
| 终止条件 | 一方全员倒下立即结束；20 轮耗尽按失败；已结束的出征不能再选路 | `battle.simulate_battle`、`run_engine.run_status` | `end_reason` 显式保存；刷新和重播不改变结果 |

## 3. 技能与羁绊触发

| 项目 | 当前实现 | 来源 | 已知限制 / 建议目标 |
|---|---|---|---|
| 技能定义 | 主动/被动均来自 `SkillDefinition`；战斗读取 `actions`，`effects` 字段当前不参与结算 | `models/battle.py`、`config/skills` | `effects` 只作为历史/展示资料，不能据此判断已实现 |
| 效果上限 | 每个技能最多 4 条动作；每条最多 6 个目标 | `BattleAction`、`SkillDefinition.actions` | 羁绊联动后仍检查 4 条上限 |
| 条件被动 | 支持 `always`、`shielded`、`target_weakened`、`first_round` | `battle.condition_matches` | 条件使用**本次行动开始时**的状态；不追溯同一次技能刚施加的降防 |
| 护盾条件 | `shielded` 看施法者行动开始时是否有护盾，不限定护盾来源 | `battle.simulate_battle` | 后羿可吃任意队友护盾；这是 T16 设计目标 |
| 降防条件 | `target_weakened` 看目标行动开始时是否已有防御减益 | `battle.simulate_battle` | 杨戬先降防、哪吒后攻击的跨角色配合可成立 |
| 羁绊激活 | 出发时按不同模板成员数判断 `requires`；只激活带 `modifiers` 的羁绊 | `run_engine.start_run`、`config/bonds` | 诗圣只有值守效果，不进入战斗羁绊 |
| 羁绊修正 | 支持加目标数、加系数、加持续时间、追加动作；追加动作属于本次施法 | `battle.simulate_battle`、`models/battle.BondModifier` | 不生成新行动，不递归触发被动/羁绊；最多 4 条动作 |
| 羁绊计数 | 战报事件记录本次触发的羁绊 ID；测量按事件计数 | `BattleEvent.bonds` | 只证明触发次数，不直接归因每条羁绊贡献的伤害 |
| 五虎 | 张飞施盾后，为关羽、赵云追加 15% 攻击 2 回合 | `config/bonds/wuhu.json` | 追加动作受 4 条动作上限约束 |
| 奔月 | 嫦娥治疗后，为后羿追加 180% 攻击护盾 2 回合 | `config/bonds/benyue.json` | 后羿护盾条件可由此稳定触发 |
| 封神 | 哪吒攻击已降防目标时多打 1 名敌人 | `config/bonds/fengshen.json` | 依赖杨戬或其他降防来源 |
| 三分天下 | 八阵图多保护 1 人；赤壁火攻降防持续 +1 回合 | `config/bonds/fensan.json` | 不增加火攻持续伤害 |
| 诗圣 | 值守修为 +10%，没有战斗 modifiers | `config/bonds/shisheng.json` | 不应在出征准备中显示为战斗羁绊 |

## 4. 资源、培养与值守

| 项目 | 当前实现 | 来源 | 已知限制 / 建议目标 |
|---|---|---|---|
| 挂机基础产出 | 修为 1/小时、灵石 0.5/小时、行动力 0.5/小时；材料按六类基础速率 | `settle.py` | 最多补算 12 小时；超出丢弃 |
| 值守加成 | 攻→修为、防→灵石、辅→行动力与伤势恢复、炼→材料；品质系数 4%/6%/9%，每点境界 +1% | `duty.py` | **等级不影响值守速率**；T18 若要“培养提升值守”，需新增规则或明确不支持 |
| 材料余量 | 小数余量写入 `material_remainders`，跨次结算累计 | `settle.py` | 取整发生在结算时，不做四舍五入 |
| 出征消耗 | 每次 1 行动力；出发即扣，胜败不退 | `tower.stamina_cost`、`run_engine.start_run` | 行动力上限受 12 小时封顶约束，没有独立硬上限 |
| 爬塔奖励 | 普通/精英/首领分别给修为、灵石、声望和材料；奖励随层数按 `reward_growth=0.1` 放大 | `tower.rewards`、`run_engine.node_reward` | 失败时待结算战利品按 `defeat_ratio=0.5` 折算，再加 `defeat_floor_reward × 已到达层数` |
| 升级费用 | 当前等级 ×20 修为、×10 灵石；无等级上限 | `progression.upgrade_cost`、`upgrade` | 费用线性增长，等级收益固定 +10% 基础属性（不含速度） |
| 境界费用 | 重复招募消耗解锁声望的 50%；破境丹可直接 +1 境界 | `recruit.REALM_UP_RATIO=0.5`、`craft.craft` | 两条入口都改变境界；T18 需同时处理，不能只限制一条 |
| 炼制 | 丹方/器方消耗材料；普通配方把永久加成写入 `state.bonuses`，疗伤/破境指定弟子 | `craft.py` | 当前多数物品是宗门共享加成，不是个人物品；T19 范围 |
| 招募 | 首次招募消耗 `unlock_cost.reputation`；重复招募转为升境界 | `recruit.py`、`config/disciples/*.json` | 新档 500 声望；六人高品质阵容的招募成本需要单独计算 |
| 伤势 | 失败后每名参战弟子 +1 层，最多 3 层；每层 4 小时消退 | `injuries.py`、`run_engine.settle_run` | 带伤可以出征/值守；疗伤丹立即清除 |
| 挂机与培养关系 | 培养消耗修为/灵石；值守提供修为/灵石/材料/行动力，但等级不提升值守 | `settle.py`、`duty.py`、`progression.py` | 当前“升级只增强战斗”，T18 需明确是否接受 |

## 5. 跨层、失败与结算

| 项目 | 当前实现 | 来源 | 已知限制 / 建议目标 |
|---|---|---|---|
| 新局气血 | 出发时按每名参战者最大气血初始化；合计气血只展示 | `run_engine.start_run`、`ActiveRun.member_hp` | `tower.start_hp=600` 是历史字段，不参与 T16 战斗 |
| 跨层气血 | 每场结束把存活者气血写回 `member_hp`；下一场从剩余气血开始 | `run_engine.choose` | 护盾、增减益、冷却每场重置；倒下者不能复活 |
| 词条改变上限 | 选到气血词条时按当前气血比例重算并向下取整 | `run_engine.pick_affix` | 不是补满血；倒下者保持 0 |
| 节点奖励 | 只有胜利节点把战利品写入 `pending_loot` | `run_engine.choose` | 失败节点不给该节点奖励 |
| 失败收益 | `pending_loot × 0.5 + defeat_floor_reward × cleared` | `run_engine.defeat_loot`、`tower.defeat_floor_reward` | 回合耗尽同样按失败；不消除已有待结算战利品 |
| 失败伤势 | 结算时给所有参战弟子 +1 层伤势 | `run_engine.settle_run` | 包括已倒下者；不删除弟子、不扣境界、不清空永久加成 |
| 塔层记录 | `tower_floor = max(旧记录, 本次到达层数)` | `run_engine.settle_run` | 20 层通关后仍可重复挑战 |
| 出征恢复 | 关闭页面/返回宗门不结束出征；刷新读取 `active_run` | `ActiveRun`、`api/run.py` | 读状态不消耗 RNG；自然消伤不改变本局快照 |
| 随机 | 路线/敌人候选/词条使用 `run_seed + rng_cursor` 的 PCG32；战斗本身不消耗随机 | `rng.py`、`run_engine` | 测量工具只推进正式决策，不额外抽随机 |

## 6. 文档、配置与实现的差异

| 差异 | 事实 | 影响 | 处理建议 |
|---|---|---|---|
| `tower.start_hp=600` | T16 已改为逐人气血，字段未删除 | 容易被误读为集体血量 | 保留兼容字段但在设计说明标注历史；T18/T20 不据此改数值 |
| `tower.damage_scale=60` | 旧总战力伤害参数，`battle.py` 不读取 | 调它不会改变战斗 | 不要把它当作平衡旋钮 |
| `base_enemy_power` / `RunNode.power` | 只用于节点展示/参考；实际敌人来自 `encounters` 的 `base_stats × (1 + step × enemy_growth)` | 只改 `power` 不会改变实际难度 | T20 调整敌人时以 `enemies/*.json` 和 `encounters` 为准 |
| `tower.segments/floors_per_segment/enemy_pool/event_pool/affix_pool/reward_table` | 当前引擎未使用或为空；词条池来自 `config/affixes` | 容易被误认为已生效 | T20/T17 文档明确标注“预留/未使用” |
| `SkillDefinition.effects` | 战斗读取 `actions`；`effects` 不参与结算 | 只看 `effects` 会误判技能已实现 | 角色工具和图鉴应继续以 `actions/implemented` 为准 |
| `BattleSummary.party_power` / `enemy_power` | T16 只作参考展示，不决定胜负 | 不能当平衡依据 | 报告以真实战报/回合/气血为准 |
| 速度成长 | `combatant` 只给 `atk/def/hp` 乘等级/境界成长，`spd` 不加 | 后期速度可能相对固定 | T18 明确是否让速度随培养成长；T20 先按当前速度设计先手 |
| 护盾消耗顺序 | 当前按状态列表顺序；同来源刷新移到末尾 | 与“来源顺序相同按稳定 ID”文字不完全一致 | 先补一条回归测试记录行为，再由 T20 决定是否改为稳定排序 |
| 治疗溢出 | 战报只记录实际治疗量 | 无法统计溢出/无效治疗 | T17 报告中明确留空；如需精细平衡，后续在战报增加请求量字段 |
| `DESIGN.md` 7.8 | 仍保留总战力/技能预览的历史描述 | 与 T16 实现不同 | 7.10 已声明替代；阅读时以 7.10 与代码为准，不在 T17 重写整份设计 |
| `state.rng_seed` | 局内使用 `active_run.run_seed`；`state.rng_seed` 不是本局随机源 | 误改全局种子不会改本局 | 不新增第二套随机源 |

## 7. 供 T18–T20 使用的结论边界

- 当前等级只增强战斗属性，不增强值守；境界同时影响战斗和值守，且可通过重复招募或破境丹进入。
- 永久加成是所有弟子共享的宗门加成；个人装备/专武尚未实现。
- 战斗结果由真实逐人回合决定；`party_power` 和 `enemy_power` 不能作为胜负或平衡结论。
- 本账本不判断哪套阵容更强；具体样本、投入和问题见 T17 报告。

## 8. 建议目标摘要（待确认，不是已修改数值）

详细依据见 [balance-report.md](balance-report.md) 第 7 节。

| 档位 | 目标层段 | 目标清关率 | 目标剩余气血 | 普通/精英/首领回合 |
|---|---:|---:|---:|---|
| 早期 1/1 | 15–20 层 | 60%–75% | 40%–60% | 2–4 / 3–5 / 5–8 |
| 中期 3/1 | 18–20 层 | 85%–95% | 60%–80% | 2–3 / 3–4 / 5–7 |
| 后期 6/1 | 20 层 | 90%–100% | 60%–80% | 2–3 / 3–5 / 7–10 |

投入参考：1→3 级约 1 次满层战利品，3→6 级约 3 次；6 级后的境界 2 当前只增加约 0.8 个百分点气血，T18 需要重新定义其阶段价值。以上目标只用于 T18–T20 复测，不先写成正式配置。
