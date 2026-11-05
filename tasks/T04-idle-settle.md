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
