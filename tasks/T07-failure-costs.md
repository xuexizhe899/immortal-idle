# T07 · 伤势、行动力与失败结算

- 里程碑：M2 ｜ 依赖：T06 ｜ 对应文档：DESIGN.md 第 7.3、7.4 节

## 目标
把失败成本落成确定规则：有张力但不产生死亡螺旋，且绝不造成永久损失。

## 已锁定决策
1. 失败扣：行动力（出发即扣）+ 补给（出发即扣，胜败不退）
2. 伤势：最多 3 层，每层 -10% 攻，**仅出征战斗内生效**，不影响挂机产出
3. `injured_until` 到期自动消退（每层约 4h，可调），疗伤丹立即清除
4. 失败也有部分收益，按到达层数计算，层数越深越多
5. 不删弟子、不掉境界、不删装备；带伤弟子可值守、不可出征；低层保底可打
6. 节奏：单局 1 点行动力，恢复约 1 点 / 2 小时起调，12h 封顶提供 ≥6 点，每天 20–30 分钟

## 要做的事
1. `injuries.py`：叠加、上限、消退、丹药清除、战斗内属性修正
2. `stamina.py`：恢复、扣除、与 T04 共用同一时钟，不写第二套计时
3. 失败结算分支：部分收益表 + 伤势挂载 + `active_run` 清理
4. 保底规则：带伤队伍仍可进入低层，保证基础收益不断粮
5. 入侵者波次规则预留：挂机积攒有上限、上线自选迎击、不迎击只损失少量资源且不产生伤势（首版仅占位）

## 产出物
- `injuries.py`、`stamina.py`、失败结算与保底测试

## 验收
- [x] 伤势不超过 3 层、每层攻击 -10%；到期自动清除，疗伤丹立即清除（`test_attack_multiplier_is_linear_and_capped`、`test_heal_clears_injury`）
- [x] 带伤不影响挂机修为与资源产出（`test_injury_does_not_affect_idle_output`）
- [x] 失败仍按层数获得部分收益，弟子、境界、装备不变（`test_defeat_grants_floor_reward`）
- [x] 连续失败不会死锁：伤势自动消退 + 每层保底收益（`test_defeat_attaches_injury`、`test_defeat_grants_floor_reward`）
- [x] 行动力恢复与挂机产出共用同一时间源：没有新建 `stamina.py`，仍在 `settle` 内一起计算

## 不做
真实时间触发的限时入侵事件、永久伤残或弟子死亡。

## 注意
"休闲"的底线是**不造成永久损失**。任何让玩家长期变弱的改动都要先回到本卡重新评估。

## 执行记录（2026-11-06）
- `app/domain/injuries.py`：`attack_multiplier`（线性，3 层封顶到 -30%）、`apply_injury`（叠加并顺延 `injured_until`）、`heal`
- `party_power` 纳入伤势，只削攻击、不动防御与气血；挂机产出完全不受影响
- 失败结算改为 `defeat_loot`：已累积战利品 × `defeat_ratio` + 每层 `defeat_floor_reward`，首层失败也能拿 3 点修为
- 新增 `POST /saves/{id}/disciples/{did}/heal`：消耗 `healing_pill`，库存不足返回 400
- 未新建 `stamina.py`：行动力恢复仍在 `settle` 内与产出一同计算，避免为单次使用拆模块（准则 3）
- 入侵者波次尚未实现，留到 T09 铺内容时按 DESIGN 7.6 补
- 测试 9 个（`backend/tests/test_injuries.py`），全库 66 passed
- 冒烟：带 2 层伤 + 1 颗丹药 → heal 后伤势 0、丹药 0；再次 heal 返回 400
