# T21 验证记录

2026-11-13。第 2 节保存原实现阶段的历史命令记录，不代表当前修复后的结果。当前复核已发现统计和解释错误，修正后的证据另列；不能沿用旧“通过”状态。

## 1. 验收逐条

| # | 验收项 | 结论 | 依据 |
|---|---|---|---|
| 1 | 每条正式词条的名称、解释、条件和真实效果一致，未实现项不进入候选 | 通过 | 20 条全部有 `type` / `description` / 生效字段；`validate_config` 校验 `type`、`condition`、`bonuses` 键与数值，`cond` 型缺 `conditional` 会报错；"连击"已改名"连锋"并如实描述为攻/速属性 |
| 2 | 三种打法均有可复现样本、适用敌情与代价 | 原结论撤回，证据不足 | 默认队伍无治疗动作，“无盾”队伍仍有护盾；旧聚合不能证明三种打法，见 `balance-report.md` |
| 3 | 至少三个同候选对照案例证明选择随状态改变 | 原结论撤回，新样本仍不足 | 六场景已重测；不同状态的部分候选已改变，当前结果不能证明三个偏好反转，详见平衡报告第 6 节 |
| 4 | 同组内具体选择得到测量 | 通过 | 新增 `tools/compare_affix_choices.py`，同组三个候选逐一 fork 跑完；策略打分已改为读 `bonuses` / `conditional`（条件打七折） |
| 5 | 重复、上限、叠加顺序、回合边界、无效目标及气血变化有规则和回归 | 通过 | 同 id 不再出现（`test_affix_options_exclude_owned`）；条件上限 35%（`test_conditional_damage_cap_is_enforced`）；减伤上限 30%（`test_taken_damage_cap_is_enforced`）；条件只看行动前状态；气血重算沿用 `pick_affix` 的比例换算 |
| 6 | 刷新恢复、CAS、响应丢失、配置变化、旧局、导入导出及快照恢复 | 通过 | 快照深拷贝测试覆盖配置变更不影响本局；旧结构与缺新字段时 `conditional_bonuses` 取默认空元组，退化为属性加成（`test_affix_options_exclude_owned` 使用旧结构 AFFIXES 仍正常） |
| 7 | 按实际改动执行相关检查 | 本轮相关检查通过 | 后端 109、工具 16、前端 27 通过，配置、RNG、契约及构建通过；准确命令见 `../../docs/reviews/2026-11-13-t18-t21-fixes.md`。第 2 节仅为历史记录 |
| 8 | 桌面与 390px 人工检查清单 | **未勾选** | 已提供清单（第 3 节），视觉由用户确认 |
| 9 | 交付设计、实现清单、对照、测试结果和限制 | 通过 | `affix-design.md`、`balance-report.md`、本文件 |

## 2. 原实现阶段的历史检查（不代表本轮修复）

| 命令 | 结果 |
|---|---|
| `cd backend && .venv/Scripts/python.exe -m pytest -q` | 158 passed |
| `cd backend && .venv/Scripts/python.exe -m pytest ../tools/tests -q` | 121 passed |
| `backend/.venv/Scripts/python.exe tools/validate_config.py` | ok：skills=32 / disciples=16 / bonds=5 / affixes=20 / materials=6 / recipes=12 / weapons=16 / modes=3 |
| `backend/.venv/Scripts/python.exe tools/check_rng_usage.py` | ok，未发现绕过 |
| `backend/.venv/Scripts/python.exe backend/scripts/export_openapi.py` | 导出成功 |
| `cd frontend && npm run gen:api` | 类型生成成功 |
| `cd frontend && npm test` | 19 passed |
| `cd frontend && npm run build` | 类型检查与构建通过 |

既有警告：后端 Starlette/httpx 弃用提示、工具测试 pytest-asyncio 配置提示，均为存量，本轮未改技术栈。

## 3. 用户人工检查清单（桌面 + 390px）

1. 出征中三选一：三条候选的效果文案是否完整可读，长文案是否溢出。
2. 已悟道法侧栏：新词条的描述是否与实际效果一致，条目变多时是否仍可滚动。
3. 条件道法（如"势如破竹""妙算"）在战报里能否看出触发时机，是否需要额外说明。
4. 刷新页面后候选是否保持不变（不应重新抽取）。
5. 等待、失败、网络错误提示是否正常；键盘 Tab / Esc 是否可用。
6. 开启"减少动态效果"后战斗播放是否正常。
7. 390px 宽度下三张候选卡是否单列、按钮是否可点。

## 4. 未执行与限制

- 未做浏览器实际渲染与视觉验收，按 AGENTS 第 8 节由用户确认。
- 未覆盖全部 20 条两两组合；本轮道法对照只有 3 个种子、6 个场景和单一培养档位，其中 B 更换一名成员，C 人工注入道法。
- 未包含专武、定向丹药与 T18 之后全部培养上限。
- 原“增伤短板”和“需要溢出机制”的结论已撤回；现有聚合没有支持这些因果解释，详见 `balance-report.md`。

## 5. 2026-11-13 测量工具修复

- 敌我治疗与护盾吸收分开统计；旧字段 `effective_healing` / `healed` / `absorbed` 表示我方，新增敌方字段。
- 人工压低气血只影响存活者，已阵亡成员保持 0。
- 历史混合治疗无逐行动事件可重算时，治疗比较为 `null`，不混用新旧口径。
- `backend/.venv/Scripts/python.exe -m pytest tools/tests/test_measure_battles.py -q`：16 passed；新增回归已先复现问题，再验证修正。仅有既有 pytest-asyncio 配置弃用提示。
- 当前代码观测已另存六份 `review-*.json`（18 条分支），完整运行方式、指纹和结果见 `balance-report.md` 第 6 节；T20 当前矩阵另存 `../t20/review-current.json`（288 次）。历史 `case-*.json` 与 T19/T20 基线未覆盖。
- 本轮工具修复和当前样本已验证；第 1 节第 2、3 项的玩法证据仍不足，不用这些固定样本宣称三打法与三个选择反转通过。后端/前端修复检查另据本轮实际命令更新，不沿用上面的历史全量检查。

## 6. 本轮代码修复

完整记录见 `../../docs/reviews/2026-11-13-t18-t21-fixes.md`。候选权重从完整词条池统计，旧局说明读取自己的定义；新增真实道法来源记录和展示，常驻、条件及减伤上限后的贡献才进入战报，旧事件缺字段时默认空。无收益生产丹、专武迟到查询和两种敌人的群体辅助目标同时修复。相关测试和构建通过，不等于第 2、3 项玩法研究或视觉验收完成。
