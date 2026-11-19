# T04 · 惰性分段结算引擎

- 里程碑：M1 ｜ 依赖：T02、T03 ｜ 对应文档：DESIGN.md 第 5 节

## 目标
实现全项目最核心的算法：无常驻 tick，读取时按 `now - last_settled_at` 惰性补算，且速率变化可分段复算。

## 已锁定决策
1. 随时间推进的只有：修为/灵石、行动力恢复、伤势消退、值守派生资源
2. `active_run` 不推进，停在等待决策的状态；关浏览器回来接着打
3. **全档推进、切档不冻结**；`frozen` 方案已作废，不得残留字段或分支
4. 12 小时软封顶，超出丢弃；不设仓库硬上限；行动力不设独立上限
5. 服务端 UTC 单调时钟；时间差为负时 clamp 为 0 并记录告警
6. 一切在读取/切档/出征时补算，不写后台定时推进器

## 要做的事
1. `settle(slot, now)`：按 DESIGN.md 5.2 伪代码实现
2. `split_by_duty_events()`：把结算区间按值守事件切成多段，逐段用 `compute_rates` 求和
3. 行动力按真实时间恢复；伤势按 `injured_until` 到期清除
4. 补算后更新 `last_settled_at`，走 T02 的 CAS 写回
5. 告警日志：时钟回拨、补算被 12h 截断、CAS 冲突

## 产出物
- `backend/app/domain/settle.py`、结算 API、完整测试集

## 验收
- [x] 幂等：同一时刻重复补算不再产出（`test_second_settle_is_noop`）
- [x] 可分段：分两次补算与一次补算结果一致（`test_split_settle_equals_single`）
- [x] 值守中途换人的分段结果与手工核算一致（`test_rate_change_midway`）
- [x] `now` 回拨不产生负产出，并写入 `logs` 告警（`test_clock_rollback_yields_nothing`）
- [x] 超过 12h 的部分被丢弃；离开 2h 后收菜数值精确匹配基础速率（`test_idle_cap_drops_extra_hours` + 冒烟）
- [x] 切档不冻结：结算只认服务端 UTC 与各自 `last_settled_at`，代码里没有冻结分支

## 不做
出征内战斗推进（T06）、前端倒计时动画（T11）。

## 注意
这是"可重算、可重放"验收的地基。任何"先跑个定时任务每秒加资源"的写法都直接违反本卡。

## 执行记录（2026-11-05）
- `app/domain/settle.py`：`rate_segments` 按 `duty_events` 切段；`settle` 原地更新 state 并返回 `SettleReport`
- 结算窗口取 `[max(last_settled_at, now - 12h), now]`，超出部分记入 `dropped_hours`
- 资源字段改为 float（按小时产出会出现小数）；行动力不设独立上限
- 伤势在 `injured_until <= now` 时清空层数与时间戳
- 告警写入 `state.logs`，限长 50 条防止存档膨胀
- 修掉一个真实 bug：时钟回拨时 `raw_hours` 归零但窗口起点未同步，导致 `elapsed_hours = -1`
- 测试 9 个（`backend/tests/test_settle.py`），全库 29 passed
- 冒烟：模拟离线 2h → 修为 +2.0 / 灵石 +1.0 / 行动力 +1.0；立即再结算 `elapsed=0.0001`、收益全 0

## 挂机累计记录修复（2026-11-19）

- 症状：在线操作先补算并推进 `last_settled_at`，随后手动同步返回的只是最近一小段区间；页面原先把该区间当成累计时长，造成不断归零的观感。现有证据没有显示这条路径漏发资源。
- `GameState.idle_record` 独立保存起止时间、累计有效时长、封顶丢弃时长与实际已入账收益，随资源和结算锚点在同一次 CAS 中提交。它是历史流水，不是第二份可领取余额，不因同步、普通操作或切档清空。
- 只汇总挂机补算结果，不混入战斗奖励、丹药或新档资源。资源保留原始精度，材料只计实际整数入库量；材料余数仍沿用原机制。
- 单段离线仍最多补算12小时；多段累计不再套总计12小时上限。时钟回拨、同刻补算和失败命令不能推进记录或重复入账。
- 新字段有默认值，旧档不需数据库列迁移；从首次成功补算开始建立记录，不能由现有余额反推出更早历史。普通快照可恢复累计记录，前端只读后台结果。
- 精确回归先红后绿：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_idle_record.py -q --tb=short`，实现前真实API链缺少记录而失败，实现后6项通过，覆盖离线后在线操作、重载、双档隔离、封顶与精度、失败/CAS竞争和回拨。
- 已有相关回归：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_settle.py backend/tests/test_garrison_production.py backend/tests/test_production_progression.py backend/tests/test_serialization_schema.py backend/tests/test_saves.py backend/tests/test_gameplay_api.py -q`，本轮50项通过；不引用上方历史全库结果作为本轮证据。
- 前端真实store与模板回归先复现累计被零增量覆盖、刷新误发补算请求，以及小额增量舍入后的误提示，再完成修复。`frontend`下执行`node --test tests/idle-record.test.mjs tests/sect-panel-navigation.test.mjs tests/game-store.test.mjs tests/page-interaction.test.mjs tests/world-dialog.test.mjs`，本轮46项通过；覆盖后台累计主展示、在线操作、只读刷新、主城提示、秒级与浮点时长边界及小额收益。
- 契约通过`backend\.venv\Scripts\python.exe backend/scripts/export_openapi.py`与`frontend`下`npm run gen:api`重新生成，未手改生成产物；`npm run build`的类型检查及生产构建通过。构建提示主城分包约554KB，超过500KB建议值，本任务未调整分包。
- 验证使用临时数据库与模拟接口，不接触真实存档；未进行浏览器渲染或视觉验收，未部署。
