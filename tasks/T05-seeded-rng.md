# T05 · 种子随机与重放

- 里程碑：M2 ｜ 依赖：T02、T04 ｜ 对应文档：DESIGN.md 第 6 节

## 目标
一条种子贯穿整局，所有随机可复现、可重放，且随机只存在于服务端。

## 已锁定决策
1. 出征开始时服务端生成 `run_seed`，整局共用；存档只存 `run_seed` + `rng_cursor`
2. 使用确定性 PRNG（PCG32 或 xorshift128），禁用 `Math.random()` 与 Python 全局 `random`
3. 消费顺序固定：地图节点 → 事件 → 词条三选一 → 敌人编成 → 战斗随机（暴击/闪避）
4. 数值公式（伤害、成长、掉落数量）纯确定性，不掺随机
5. 随机全在服务端，前端只渲染，无需 JS/Python 双端对齐

## 要做的事
1. `backend/app/domain/rng.py`：种子初始化、按类型取值、游标推进与序列化
2. 各类随机调用统一走该模块，禁止散落调用其他随机源
3. 加权三选一：每选定一个词条，其协同组后续权重 +50%（可叠加），单次不重复
4. 重放能力：给定 `run_seed` + 决策序列，重算整局并输出比对结果（先做接口/测试，不做 UI）
5. 在 CI 中加一条静态检查，拦截 `Math.random` / `import random` 的直接使用

## 产出物
- `rng.py`、加权抽取模块、重放与一致性测试

## 验收
- [x] 同 seed + 同调用序列 → 结果完全一致（`test_same_seed_gives_same_sequence`、`test_draw_is_reproducible`）
- [x] 不同 seed 产生不同序列（`test_different_seed_differs`）
- [x] 游标可存档、可恢复，续玩后序列不间断（`test_advance_to_resumes_sequence`）
- [x] 随机只作用于"选什么"，现有数值公式（结算）纯确定性；property-based 留到 T06 战斗公式
- [x] 代码库无绕过：`tools/check_rng_usage.py` 已接入 CI 的 config job

## 不做
重放调试界面（首版砍项）、任何前端随机。

## 注意
新增随机调用点必须插入固定消费顺序，否则老存档重放会整体错位；顺序变更要记录并重测。

## 执行记录（2026-11-05）
- `app/domain/rng.py`：手写 PCG32，预热两轮，`cursor` 记录累计消耗；`advance_to` 用于从存档恢复
- `app/domain/affix.py`：`weights_for` 按协同组加权（同组每条 +50%），`draw` 按权重不放回抽三条
- `tools/check_rng_usage.py`：扫 `backend/app` 与 `frontend/src`，拦截 `import random` 与 `Math.random`，已接入 CI
- 测试 10 个（`backend/tests/test_rng.py`），全库 39 passed
- 整局重放要等 T06 的 run_engine 接入，当前已保证随机流可按 `(seed, cursor)` 精确恢复
