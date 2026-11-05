# T06 · 出征状态机与战斗结算

- 里程碑：M2 ｜ 依赖：T04、T05 ｜ 对应文档：DESIGN.md 第 7.1、7.2、7.6 节

## 目标
跑通一次完整出征：组队 → 节点 → 加权三选一 → 自动战斗 → 按层数结算 → 战利品原子写回永久层。

## 已锁定决策
1. 一局 = 一次出征；局外永久层永不重置，局内 `active_run` 结束即清空
2. 状态机：`idle → preparing → node_choices → affix_choice → battle → … → cleared|defeated → settle`
3. 单局 3–5 分钟 / 8–12 节点；纯自动战斗，玩家只在节点与词条处决策
4. 出征带走队伍快照 + 补给 + 1 点行动力 + `run_seed`；弟子本体不消耗，期间标 `busy`
5. 中途关闭浏览器不算失败，`active_run` 原样保留、可恢复
6. 爬塔/远征/入侵者共用引擎，**仅配置表不同**；首版只要求爬塔可玩

## 要做的事
1. `run_engine.py`：状态机、节点生成、词条三选一、自动战斗、层数推进
2. 出发校验：队伍 3–5 人、不与值守重叠、补给与行动力扣除、生成 seed
3. 结算：按到达层数计算部分收益，一次性原子写回永久层，清空 `active_run`，解除 `busy`
4. `active_run` 完整入 `state_json`（含 `run_seed`、`rng_cursor`、`pending_loot`）
5. `config/modes/tower.json` 接入；`expedition.json`、`invasion.json` 仅占位不影响爬塔

## 产出物
- `run_engine.py`、出征 API、模式配置接入、整局与重放测试

## 验收
- [x] 能从组队打到结算，战利品正确进入永久层且只写一次（`test_defeat_settles_half_loot`、`test_clear_settles_full_loot` + 冒烟）
- [x] 中途关闭浏览器后恢复：`active_run` 随存档序列化，往返后节点 / 游标 / 待选词条不丢（`test_run_survives_serialization`）
- [x] 同一 `run_seed` 重放结果一致（`test_same_seed_and_decisions_replay_identically`）
- [x] 出征中弟子无法编入值守或另一支队，结束后恢复可用（`test_assign_rejects_busy_disciple`、`test_start_run_rejects_busy_disciple`、`test_settle_clears_busy`）
- [x] 切换模式不需改引擎：层数 / 初始血量 / 敌人强度 / 精英概率 / 行动力消耗 / 奖励全部来自 `config/modes/tower.json`（`test_node_count_comes_from_mode`、`test_tower_config_has_fields_engine_needs`）

## 不做
伤势与失败惩罚细节（T07）、前端演出（T11）、远征/入侵的实际内容（首版占位）。

## 注意
结算必须是**一次原子写入**，不允许"边打边入账"，否则中途退出会产生半状态存档。

## 执行记录（2026-11-05）
- `app/domain/run_engine.py`：节点生成、确定性战斗、状态推导、开始 / 选路 / 选词条 / 结算
- 模型：`ActiveRun` 增加 party / hp / choices / affix_options / affix_pending；新增 `RunNode`；`DiscipleState.busy` 取代 `busy_until`
- 参数全部来自 `config/modes/tower.json`，换模式不改代码
- `app/api/run.py`：5 条路由（查看 / 开始 / 选路 / 选词条 / 结算），未结束就结算返回 400，写回走 CAS
- 测试 18 个（`backend/tests/test_run_engine.py`），全库 57 passed
- 冒烟：start 后 hp 300、2 个候选；提前结算 400；选路后首层即失败；settle 后 busy 解除、行动力 3→2
- 数值平衡留给 T09：诸葛亮单人战力 26.1 打不过首层 30，属预期而非 bug
