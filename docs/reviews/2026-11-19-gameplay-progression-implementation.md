# 个人装备与地区推进 · 实现审查记录

日期：2026-11-19。状态：首版代码与相关检查已完成，32个隔离新档的首轮测量、二区有限探针及主殿升级/同档配队探针已完成；人工玩法与视觉体验未验收，未部署。本记录区分功能实现、自动化证据与人工验收，不将单个测试或模拟批次视为最终平衡和发布验收。

当前数值入口见[经营数值基线](../sect-economy-baseline.md)，玩法说明见[DESIGN](../../DESIGN.md)，成长证据见[首区模拟与二区探针](2026-11-19-progression-simulation.md)。后续数值、奖励预览和界面修改应按实际影响重新检查。

## 已接入规则

### 个人装备

- 普通装备分武器、盔甲、靴子、戒指四槽，当前每槽两个模板；每件一个副属性，轻随机分三档。阶位、主副属性、成长步长与强化投入随实例保存。
- `GameState.gear` 保存已拥有实例，`DiscipleState.gear_slots` 保存穿戴关系。同一实例不能同时由多人穿戴，可替换或转穿；普通武器与既有专武互斥。普通器方不再制造或升级宗门公共收益，专武保留锻造与逐级升级，丹药继续走既有流程。
- 装备战斗属性只作用于穿戴者；装备中的生产属性只影响该弟子对应的值守或驻守贡献，不把个人收益写回全宗门公共增益。出征者的装备不能换装、强化或洗练，本局读取出发快照。
- 炼器阁等级开放普通装备+3/+6/+9上限；强化按实例已保存的步长增加主属性，消耗炼器精粹。洗练扣费后保存候选，玩家选择保留旧属性或采用新属性，确认不再扣费或重抽；未确认候选前不能再次洗练或强化。
- 秘境与问道塔的新局支持掉装，首领胜利必掉，普通/精英轻随机。生成结果先进入 `active_run.pending_gear`，结算后才成为可穿戴或熔炼的库存；秘境失败保留已获资源及装备，塔失败按模式折算资源、待结算装备仅通关带回。

### 地区与长期推进

- 当前两个地图图层为云岚下界、青冥灵域，各三个片区。宗门占据固定位置，每个已开放地区随主殿等级开放3/6/9座，仍受片区门槛限制。
- 宗门征讨保留3–6人随行、每场3人、最多三轮擂台、破守备后3v1宗主，消耗2行动力。攻克后可驻守产材，亦可消耗2行动力重复论道；论道胜利发固定奖励、失败零奖励，不重复首胜。
- 每片区两处六段秘境、守关与关键入侵。秘境消耗2行动力，守关1，普通迎击、关键入侵和演练0；问道塔费用读取当前配置与同源服务端预览，不在文档中固化调校中的覆盖值。
- 普通迎击按服务端时间积攒敌情，当前每4小时一波、上限3波、初始1波。玩家主动选择接战，不接战不会扣资源或造成伤势；正式胜利才消耗一波并提高后续难度，失败保留该波。达到敌情上限后不会暗中积攒额外波次。
- 击败守关开放下一片区；关键入侵需要本片区守关和前一片区关键入侵完成。地区最终关键入侵首胜获得升仙令，消耗一枚开放下一地区；重复命令受CAS保护，不重复扣令。
- 免费切回已开放地区，保留弟子、装备、资源、旧区驻守与塔记录。问道塔按地区分别保留三阶、每阶20层进度，设施等级和前阶真正通关共同限制后阶。
- 开放第二地区后，培养范围续接至20级、境界6；境界1–6对应等级上限3/6/10/13/16/20。能力按最高已开放地区计算，回旧区不收回成长上限。
- 挂机继续提供基础资源，新增炼器精粹产出；主动秘境、征讨/论道与迎击加快积累。当前问道塔三点行动力，原塔基础奖励及失败保底按0.65倍调整；秘境补充突破声望。地图策略的首轮模拟支持约一周目标，具体操作时间和趣味性仍须人工试玩。

## 关键结算边界

### 熔炼的80%范围

熔炼返回两部分：配置规定的本体精粹，以及 `invested` 中每种资源累计可返投入的 `count * 4 // 5`，逐种向下取整后相加。当前本体精粹为 `2 × 装备阶位`；强化消耗会记录到 `invested`，洗练费不记录、不返还。可识别旧器具的历史制造投入在迁移时纳入记录。

因此不能描述成“所有历史消耗一律返回80%”，也不能将本体精粹当成强化费用全额返还。已穿戴、锁定或存在待确认洗练候选的装备不能熔炼；专武不在普通装备熔炼范围。

### 演练

仅普通迎击、关键入侵与守关支持演练。仍校验地区/片区开放和真实队伍条件，普通迎击没有待迎击敌情时可演练。演练使用真实战斗快照与战报，但不发资源、装备或升仙令，不增加伤势，不消耗敌情，也不推进正式首胜、波次或片区；胜败都遵守该边界。

演练仍走正常出发/结算的岗位占用与恢复流程，不允许同一弟子同时出征、值守和驻守。关闭页面、返回宗门或刷新不视为失败，不重抽已经生成的输入。

### 旧档与旧局

- `prepare_mutation` 先按旧速率补算离线区间，再执行普通器具迁移，最后记录新个人产出；不会把迁移后的个人速率追溯应用到旧离线时间。
- 已知六个旧普通器具按制造记录、等级和可解释公共增益转为个人实例；只扣除可解释的非负部分，保留未知余量、未知旧器具和既有个人丹药加成。`equipment_version` 保证只迁移一次，不重复发装或返还。
- 已开始且结构可识别的旧十二段远征、路线版本与战斗快照继续结算；未固化 `equipment_rules` 的旧局不额外生成掉装随机消耗。该范围不等同于兼容所有T16之前的原型结构。
- 出征保存固定队伍/装备/配置快照和 `run_seed`、`rng_cursor`；自然消伤、换区、配置修改和重播不会改变已经开始的战斗输入。洗练独立保存 `gear_rng_cursor`，候选确认不再次消费随机。
- 时钟回拨不能增加收益、回退结算锚点或缩短新伤势；产出变更仍先补算旧区间并原子保存。所有有消耗的命令使用 `revision`，结果不确定时只查询最新状态，不自动重发扣费命令。

## 关键文件

| 范围 | 文件与职责 |
|---|---|
| 配置 | `config/equipment.json`：普通装备与精粹费用；`config/world.json`：地区、敌情、节点与奖励；`config/facilities.json`：设施费用及成长上限 |
| 新材料 | `config/materials/lian_qi_jing_cui.json`、`config/materials/sheng_xian_ling.json`；对应本地SVG与道具清单 |
| 契约与存档 | `backend/app/models/equipment.py`、`world.py`、`save.py` 及 `models/api.py`；整档 `state_json` 与CAS保持不变 |
| 装备领域 | `backend/app/domain/equipment.py`：归属、掉落、强化、洗练、熔炼和旧器具迁移；`weapons.py`、`craft.py`：专武互斥与旧普通器方停用 |
| 世界领域 | `backend/app/domain/world.py`：地图投影、敌情、节点快照、首胜与飞升；`conquest.py`：地区宗门与论道 |
| 出征与经济 | `backend/app/domain/run_engine.py`：快照、机缘、待结算装备、模式收益与地区塔记录；`duty.py`、`settle.py`、`progression.py`、`training.py`：个人贡献与成长 |
| 接口 | `backend/app/api/equipment.py`、`world.py`、`run.py`、`state.py`、`saves.py`、`duty.py`；`backend/app/main.py` 注册入口 |
| 前端 | `frontend/src/views/EquipmentPanel.vue`、`WorldPanel.vue` 与既有炼器/弟子/出征面板；`components/game/GearIcon.vue`、`presentation/equipment.ts`、`stores/game.ts`、`api/client.ts` |
| 配置与模拟工具 | `tools/validate_config.py`、装备/世界配置测试及 `tools/simulate_world_progression.py`；模拟输出用于调校，不作为玩家体验验收 |

前端入口已接入不代表视觉验收完成；桌面、390px、长文案、弹窗、加载/失败反馈、键盘可用性与减少动态效果偏好仍由用户人工检查。

## 本轮审查发现

曾复现第二地区爬塔完成后更新全局旧 `tower_floor`，导致回一区误开放二阶塔的问题；已收窄为仅一区更新该兼容字段，地区记录仍各自保存。定向回归 `test_second_region_tower_does_not_unlock_first_region_tier_two` 已通过，并纳入后续相关检查。

旧局额外只读对照使用 `HEAD` 中旧 `run_engine.py` 与本轮实现：路线版本1、2分别继续四场真实战斗与道法选择，不含新装备规则时完整 `active_run` 一致，最终随机游标分别为28、33。这是有限样本，不是所有历史结构兼容性证明。

## 已有验证证据

以下是正式数值与最终代码下的本轮检查；只检查受影响模块，没有执行游戏全量测试或浏览器渲染检查。

| 检查 | 实际结果 |
|---|---|
| 相关后端17个文件，含存档/序列化、装备、世界、出征、培养、驻守和挂机 | 202 passed in 5.60s，退出0 |
| 配置、图标与模拟工具4个文件 | 39 passed in 0.67s，退出0 |
| 相关前端10个文件 | 83/83通过，退出0 |
| `npm run build` | TypeScript与Vite生产构建通过；既有主城分包554.04kB提示保留 |
| `tools/validate_config.py`、`tools/check_rng_usage.py` | 均退出0 |
| OpenAPI导出、`npm run gen:api` | 均退出0；生成产物按仓库规则不手改、不提交 |
| `backend\.venv\Scripts\python.exe artifacts/progression/checkpoint-probes.py` | 退出0，6.15s；补记主殿二/三级升级即时库存与可出发内容、同一真实培养存档的两组三人论道战果，配置和原模拟工具未改 |

最终后端命令：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_equipment.py backend/tests/test_equipment_api.py backend/tests/test_weapons.py backend/tests/test_craft.py backend/tests/test_facilities_crafting.py backend/tests/test_gameplay_api.py backend/tests/test_conquest.py backend/tests/test_production_progression.py backend/tests/test_run_party_snapshot.py backend/tests/test_run_engine.py backend/tests/test_duty.py backend/tests/test_settle.py backend/tests/test_world_run_api.py backend/tests/test_world.py backend/tests/test_world_growth.py backend/tests/test_saves.py backend/tests/test_serialization_schema.py -q --tb=short
backend\.venv\Scripts\python.exe -m pytest tools/tests/test_generate_item_icons.py tools/tests/test_validate_equipment.py tools/tests/test_world_config.py tools/tests/test_simulate_world_progression.py -q --tb=short
```

前端目录下执行：

```powershell
node --test tests/asset-paths.test.mjs tests/battle-playback.test.mjs tests/equipment-world-store.test.mjs tests/equipment.test.mjs tests/expedition.test.mjs tests/game-store.test.mjs tests/game-text.test.mjs tests/goal-chain.test.mjs tests/sect-management.test.mjs tests/world-navigation.test.mjs
npm run build
```

其后仅调整失败指引文案，并再次完成生产构建。工具测试出现既有 `pytest_asyncio` 默认事件循环范围弃用提醒，未改动无关测试配置。

以下保留中间批次，便于追溯，最终结果以上表为准。

### 个人装备与集成边界批次

从仓库根目录执行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_equipment.py backend/tests/test_equipment_api.py backend/tests/test_weapons.py backend/tests/test_craft.py backend/tests/test_facilities_crafting.py backend/tests/test_world_run_api.py backend/tests/test_gameplay_api.py::test_normal_artifact_cannot_regrant_global_bonuses tools/tests/test_validate_equipment.py -q --tb=short
```

结果：**81 passed in 4.50s，退出状态0**。

其中 `test_world_run_api.py` 的15项集成用例覆盖地图GET只读、锁区失败原子性、旅行/飞升CAS、零行动力正式迎击、三类演练胜败无永久奖励/新伤势、秘境先胜后败保留且仅结算一次、个人收益隔离、装备/掉落规则出发快照、换生产装先补算、旧器具幂等迁移与回拨锚点，以及跨区驻守和塔记录。

同阶段的 `tools/validate_config.py` 检查通过，15种材料引用有效；`tools/check_rng_usage.py` 通过，个人装备相关改动的 `git diff --check` 通过。以上均不是后续数值修改之后的新结果。

### 后端相关模块集成中间批次

从仓库根目录执行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_equipment.py backend/tests/test_equipment_api.py backend/tests/test_weapons.py backend/tests/test_craft.py backend/tests/test_facilities_crafting.py backend/tests/test_gameplay_api.py backend/tests/test_conquest.py backend/tests/test_production_progression.py backend/tests/test_run_party_snapshot.py backend/tests/test_run_engine.py backend/tests/test_duty.py backend/tests/test_settle.py backend/tests/test_world_run_api.py backend/tests/test_world.py backend/tests/test_world_growth.py -q --tb=short
```

结果：**191 passed in 5.40s，退出状态0**，覆盖15个相关后端测试文件。该批次之后计划继续调整秘境基础声望与首周数值，并接入同源的地区塔/论道奖励预览；最终验证应以这些变更完成后的批次为准。

## 尚未完成的验收

- 首轮端到端模拟完成，但只覆盖固定招募阵容与明确策略；补充的同档两组三人论道对照不替代其他招募路线测量。地图30分钟预算八个种子均在第5–7天得令牌；60分钟预算第5–6天，塔优先第4–5天；三组第7天均24槽。偏挂机每天一次/10分钟十天内仍未得令牌，不能宣称所有参与强度均一周闭环。
- 早期开区偏快、塔优先更富、地图策略未用满60分钟预算等限制保留，详见模拟报告；后续不以局部模拟替代长期平衡和不同阵容试玩。
- 玩家人工体验：重复刷取是否有有意义的装备选择、普通迎击递增是否形成可接受压力、无行动力时是否仍有适度可玩内容、飞升后是否保持继续培养目标。
- 视觉与交互由用户人工验收，本轮未进行浏览器渲染或视觉验收。
- 本轮未对用户真实存档执行演示改写、重建或降级，未调用付费生图；代码未部署，提交和推送状态以最终交付及Git记录为准。
