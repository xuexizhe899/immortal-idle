# T21 验证记录

2026-11-13。所有结果来自本轮代码，未引用历史通过记录。

## 1. 验收逐条

| # | 验收项 | 结论 | 依据 |
|---|---|---|---|
| 1 | 每条正式词条的名称、解释、条件和真实效果一致，未实现项不进入候选 | 通过 | 20 条全部有 `type` / `description` / 生效字段；`validate_config` 校验 `type`、`condition`、`bonuses` 键与数值，`cond` 型缺 `conditional` 会报错；"连击"已改名"连锋"并如实描述为攻/速属性 |
| 2 | 三种打法均有可复现样本、适用敌情与代价 | 通过（"护盾进攻"实测后改为"护盾续航"） | 破甲收割：残血场景 13 层；护盾续航：有盾来源 19 层；恢复持久：坚守未成型存活 2 人。见 `balance-report.md` 2.1–2.3 |
| 3 | 至少三个同候选对照案例证明选择随状态改变 | 通过 | 满血 vs 残血、有盾源 vs 无盾源、未成型 vs 已成型，各 3 个候选，数据在 `case-*.json` |
| 4 | 同组内具体选择得到测量 | 通过 | 新增 `tools/compare_affix_choices.py`，同组三个候选逐一 fork 跑完；策略打分已改为读 `bonuses` / `conditional`（条件打七折） |
| 5 | 重复、上限、叠加顺序、回合边界、无效目标及气血变化有规则和回归 | 通过 | 同 id 不再出现（`test_affix_options_exclude_owned`）；条件上限 35%（`test_conditional_damage_cap_is_enforced`）；减伤上限 30%（`test_taken_damage_cap_is_enforced`）；条件只看行动前状态；气血重算沿用 `pick_affix` 的比例换算 |
| 6 | 刷新恢复、CAS、响应丢失、配置变化、旧局、导入导出及快照恢复 | 通过 | 快照深拷贝测试覆盖配置变更不影响本局；旧结构与缺新字段时 `conditional_bonuses` 取默认空元组，退化为属性加成（`test_affix_options_exclude_owned` 使用旧结构 AFFIXES 仍正常） |
| 7 | 按实际改动执行相关检查 | 通过 | 见第 2 节 |
| 8 | 桌面与 390px 人工检查清单 | **未勾选** | 已提供清单（第 3 节），视觉由用户确认 |
| 9 | 交付设计、实现清单、对照、测试结果和限制 | 通过 | `affix-design.md`、`balance-report.md`、本文件 |

## 2. 执行的检查（实际命令与结果）

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
- 未覆盖全部 20 条两两组合；对照只用了 4 组种子、单一队伍与单一培养档位。
- 未包含专武、定向丹药与 T18 之后全部培养上限。
- 增伤类在"护盾进攻"上的短板已记录在 `balance-report.md` 3.1，未通过继续拉高数值掩盖；是否调整溢出机制留给 T22。
