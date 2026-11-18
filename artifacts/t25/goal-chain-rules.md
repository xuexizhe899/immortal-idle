# T25 · 目标链与资源可见性规则稿

2026-11-18（北京时间）。状态：用户已确认本轮实施范围含单场论道（P0 v2）与三项显示接通；本稿为实施依据，验证结果见交付说明。论道玩法口径以 [P0 v2](../../docs/plans/2026-11-14-p0-repeatable-challenge.md) 为准，本稿只记录落地决策与展示契约。

## 一、链路与数据来源

| 链路 | 数据来源 | 计算定义 | 缺失行为 | 跳转 | 保存 |
|---|---|---|---|---|---|
| 论道 | `start_run` 固化 `retrial_reward`；`settle_run` 读快照 | 胜利发固定表、失败零；不碰 conquered | 旧局 `is_retrial` 缺省 False 走原征讨分支 | 远行码头已攻克宗门 dossier | 仅 ActiveRun/RunReview 新增带默认值字段 |
| 来源矩阵 | catalog（production.materials、disciples.specialty、mode.rewards、sect_styles）+ state.sects | 速率与一次性分开；纯展示换算 | 无主动来源如实列挂机/值守；论道未开放标"未开放" | 复用 planProduction / open(panel) | 不写存档 |
| 收取接通 | settle 后 previewFacilities + previewRecipes(1) | 优先级：可升级设施 > 设施缺料 > 可炼配方 > currentGoal | 预览失败回落 currentGoal，不伪造 | open(sect/alchemy/forge) | 不写存档 |
| 分配总览 | 新 GET duty/assignments | personal_duty_rates + 单人驻守公式；post 四态 | 旧档无驻守/值守正常显示 idle | 值守/驻守原入口 | 只读，不改 revision |

## 二、论道落地决策

- 配置：`config/sects.json` 三流派增 `retrial_reward`：剑修 `{chi_tong:4, spirit_stone:10}`、御守 `{qing_shi:14, spirit_stone:11}`、丹修 `{ling_mu:8, spirit_stone:11}`。`validate_config.check_sects` 校验键属于材料或灵石、值为正有限数、材料为正整数。
- 存档：`ActiveRun.is_retrial: bool=False`、`ActiveRun.retrial_reward: dict[str,float]={}`；`RunReview.is_retrial: bool=False`。旧档缺省走原逻辑。
- 出发：`StartRunRequest.is_retrial`；API 校验 mode=expedition 且宗门存在，按 `sect.style` 从配置取奖励传入 `start_run`。`start_run`：已攻克且非论道 → "该宗门已攻克，可安排驻守或论道"；论道且未攻克 → "论道仅面向已攻克的宗门"；论道奖励为空 → "论道奖励未配置"。论道 `guard=0`（首战即 3v1 宗主）、`frozen_mode.node_count=1`；其余快照、离岗、扣 2 行动力沿用征讨。
- 战斗：`conquest.arena` 宗主胜时 `loot = run.retrial_reward if run.is_retrial else sect.loot`，节点奖励与战报同源。
- 结算：`settle_run` 宗门分支按 `is_retrial` 独立：胜利发 `retrial_reward`、失败零；不读 `sect.loot`、不改 `conquered`。伤势/回岗沿用（失败仅参战者一层）。
- 展示契约：`CatalogResponse.sect_styles: [{name,suffix,retrial_reward}]`；`ModeCatalog.rewards: dict[str,dict[str,float]]`（默认 {}，塔掉落展示用）。
- 前端：ExpeditionPanel 已攻克 dossier 增论道块（固定奖励、宗主情报、随行队伍、出发按钮 is_retrial）；ConquestRun 按 is_retrial 切换标题/守备区/战利品面板/结束与撤退文案；SectPanel 复盘与 CityView 行程文案区分论道。

## 三、材料来源矩阵（13 种：10 基础 + 3 专材）

纯函数 `presentation/materialSources.ts` 生成，组件 `MaterialSources.vue` 渲染，入口为 SectPanel 新页签"材料来源"（不新增底栏）。

| 来源 | 判定 | 口径 |
|---|---|---|
| 挂机基础 | catalog.production.materials[id] > 0 | 速率/时 |
| 值守专长 | 弟子 production_specialty == id | 速率 = 基础时产 × 演武倍率(1+0.25×(级-1))，列专长弟子名 |
| 外宗驻守 | state.sects 的 material_id/special_material_id == id | 速率 0.5×阶 / 0.15×阶，专长匹配翻倍；未攻克标"需先攻克" |
| 问道塔 | catalog.mode.rewards 各 kind 含 id | 一次性/每胜场，列普通/精英/首领 |
| 征讨首胜 | state.sects.loot 含 id | 一次性，列宗门名 |
| 论道 | catalog.sect_styles.retrial_reward 含 id | 一次性/每胜场；该流派无已攻克宗门时标"未开放" |

跳转：挂机/值守 → duty；驻守/首胜/论道 → expedition（planProduction 已带 targetSectId）；塔 → tower。不发起请求、不扣费；来源 ID 全部来自 catalog/state，无悬空。

## 四、收取接通

`presentation/nextAction.ts` 纯函数：输入 facilities/recipes/catalog，输出 `{label, panel}` 或 null。优先级：`upgradeable` 设施 → 首个缺料设施（列所缺资源名）→ `max_quantity>0` 配方（丹→alchemy、器→forge）→ null。CityView 在 lastSettle 变化时经 previewFacilities/previewRecipes(1) 各取一次（readPreview 防串档），null 时不显示额外浮签（currentGoal 已在）。点击只 open 面板，不发命令。

## 五、分配总览

- `duty.py` 抽出 `member_garrison_rates(sect, disciple, template)`（0.5/0.15 × 阶 × 匹配2），`garrison_production` 复用，预览与结算同一公式。
- 新 GET `/saves/{slot_id}/duty/assignments` → `{revision, assignments:[{disciple_id, post: duty|garrison|run|idle, sect_id?, duty_rates, garrison_rates}]}`。只读 `repo.get_state`，不补算不写回（同 facilities 预览）。duty_rates 为个人值守潜力（含演武倍率），garrison_rates 仅当前驻守者非空。
- DutyPanel 增"分配总览"表：岗位、值守贡献（修为/灵石/行动力/材料加成与专长时产）、驻守贡献；驻守者显示"改值守得 X、失驻守 Y"的差值说明（纯展示）。加载随 revision/slot 刷新。

## 六、契约增量与生成

ActiveRun、RunReview、StartRunRequest、CatalogResponse、ModeCatalog、AssignmentView/AssignmentListResponse。改后执行 `backend/scripts/export_openapi.py` + `npm run gen:api`，生成产物不手改。

## 七、验证计划

- 后端：test_conquest/test_run_engine 增论道回归（出发校验、guard=0、奖励快照、胜利/失败结算、conquered 不变、旧局兼容、CAS）；test_duty 或新测试覆盖 assignments 只读与公式一致；catalog 测试覆盖 sect_styles/rewards。
- 工具：validate_config（含 retrial_reward 校验）、check_rng_usage（论道不新增随机消费）。
- 前端：material-sources/nextAction 纯函数测试；game-store 论道参数透传；相关测试 + build。
- 实测：隔离测试档跑 P0 v2 §5 两类案例（零库存三论道升主殿+塔；正常流水记账），不碰用户真实存档。
- 视觉：桌面/390px 由用户人工验收。

## 八、边界

不新增货币/模式/任务/限时/多人；史墙等储备不在本轮；12h 封顶与伤势规则不动；前端不另算产出真值；预览失败不伪造；论道失败零奖励与塔失败折算口径分开。