# T03 · 值守编制与产出速率

- 里程碑：M1 ｜ 依赖：T02 ｜ 对应文档：DESIGN.md 第 7.5 节

## 目标
实现"宗门值守"编制，让挂机产出速率随编制变化，并把每次变更记入事件流供分段结算。

## 已锁定决策
1. 编制上限 6 人，**与出征队伍互斥**；带伤弟子可值守、不可出征
2. 四倾向映射四样挂机产出：攻→修为，防→灵石，辅→行动力恢复与伤势消退，炼→材料/丹药产出
3. 品质档定系数、境界定基础值，**走加区 +%，不做乘区**
4. 每次变更写入 `duty_events`（`at` + 当时编制快照），结算按事件分段求和
5. 每个存档槽位各自一份编制与事件流

## 要做的事
1. 编制接口：上岗、下岗、替换、查询；互斥与上限校验（出征中/已在值守/超过 6 人）
2. `compute_rates(snapshot, disciples)`：输出四类产出的速率与恢复修正
3. 变更时追加 `duty_events`，保留当时快照，不覆盖历史
4. 速率公式做成纯函数，配置化系数，便于 property-based 测试
5. 与 T02 的 `state_json` 字段对齐：`duty_slots[]`、`duty_events[]`

## 产出物
- `backend/app/domain/duty.py`、编制 API、速率公式与测试

## 验收
- [x] 出征中的弟子拒绝上岗、同一弟子不可重复上岗；第 7 人上岗被拒（`test_duty_capacity_is_six`）
- [x] 每次变更追加一条事件，历史事件只读不改（`test_unassign_removes_slot_and_records_event`）
- [x] 同一编制速率确定；四倾向分别影响对应产出（含辅倾向同时影响行动力与伤势）
- [x] 加成只走加区：两名同倾向弟子相加，不做乘法叠加（`test_rates_are_additive_not_multiplicative`）

## 不做
分段补算本身（T04）、前端编制界面（T11）。

## 注意
速率必须是**纯函数**，不能在读档时偷偷改状态；否则 T04 的可重放与幂等测试会失效。

## 执行记录（2026-11-05）
- `app/config_loader.py`：`load_disciples()` 用 `lru_cache` 常驻内存，运行期不重读磁盘
- `app/domain/duty.py`：`compute_rates` 是纯函数；四倾向映射五个键（辅倾向同时给 `stamina_rate` 与 `injury_rate`）；品质系数 + 境界加成，全走加区
- `assign` / `unassign` 负责互斥、上限、busy 校验，成功后 `record_event` 追加 `duty_events` 快照
- `app/api/duty.py`：3 条路由（查看 / 上岗 / 下岗），变更带 revision 走 CAS，冲突 409、业务错误 400
- 冒烟实测：诸葛亮（rarity 3 / realm 2）上岗后 `stamina_rate = injury_rate = 0.11`（0.09 + 0.02），重复上岗返回 400
- 测试 11 个（`backend/tests/test_duty.py`），全库 20 passed；契约新增 3 条路由，前端 build 通过
