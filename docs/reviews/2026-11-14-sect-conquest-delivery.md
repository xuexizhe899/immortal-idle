# 宗门征讨与设施经营交付记录

日期：2026-11-14。实施依据为用户确认的 Q1–Q27 和 [实施基线](../plans/2026-11-14-sect-conquest-and-facilities.md)。本轮未部署，未使用付费生图，未操作用户真实数据库。

## 代码结果

- 远行改为规则组合生成的固定 NPC 宗门。随主殿开放3/6/9座；带3–6人，每场选三人，最多三轮擂台，按存活人数削减守备，破防后挑战宗主。首胜奖励一次发放，攻克后可派0–3人驻守。
- 出征和岗位调度在服务端一次命令内处理；结算自动回原岗位，容量冲突不替换现有人选，气泡及日志说明未回岗成员。
- 五座设施最高三级，主殿限制其他设施上限。器具和专武逐件升级，属性丹按强化名额补高阶差额；问道更高阶要求设施等级与前阶真正通关。
- 炼丹支持数量、最大可炼和品级。队伍疗伤优先库存，按缺额补炼并统一治疗；不足时按伤势与队列尽可能治疗。
- 16名弟子各有一项生产专长。新增四种基础材和三类专材，外宗按资源倾向生产。个人培养预览与实际值守共用产出计算。
- 主殿、炼制、整备、远行和擂台使用正式状态与服务端预览；藏经阁更名弟子堂。原 T24 独立静态样板保留历史身份，不作为当前视觉验收依据。
- 七种新材料使用可复现 SVG；NPC守军和宗主复用本地敌人素材，并将图片键写入快照。接口类型重新从 Pydantic 生成。

## 主要代码入口

| 内容 | 文件 |
|---|---|
| 固定外宗、擂台及撤退 | `backend/app/domain/conquest.py`、`backend/app/domain/run_engine.py`、`backend/app/api/run.py` |
| 原子调度、驻守与分段产出 | `backend/app/domain/deployment.py`、`duty.py`、`settle.py`、`backend/app/api/garrison.py` |
| 设施、器具、丹药、专武 | `backend/app/domain/facilities.py`、`craft.py`、`items.py`、`weapons.py` 及对应 API |
| 新存档字段与接口 | `backend/app/models/save.py`、`api.py`、`backend/app/api/state.py` |
| 正式经营与征讨页面 | `frontend/src/components/game/FacilitiesSection.vue`、`PartyHealing.vue`、`frontend/src/views/CraftPanel.vue`、`ExpeditionPanel.vue`、`ConquestRun.vue` |
| 配置与数值说明 | `config/facilities.json`、`config/sects.json`、[经济数值基线](../sect-economy-baseline.md) |

## 验证记录

只运行本次影响范围，未执行全仓测试、浏览器渲染或视觉验收。

后端在 `backend` 目录执行，退出0，**190项通过**：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_conquest.py tests/test_expedition_api.py tests/test_run_engine.py tests/test_run_party_snapshot.py tests/test_t22_routes.py tests/test_t22_api.py tests/test_run_review.py tests/test_gameplay_api.py tests/test_garrison_production.py tests/test_duty.py tests/test_settle.py tests/test_serialization_schema.py tests/test_craft.py tests/test_items.py tests/test_weapons.py tests/test_facilities_crafting.py tests/test_economy_api.py tests/test_production_progression.py -q
```

工具在仓库根目录执行，退出0，**119项通过**：

```powershell
backend\.venv\Scripts\python.exe -m pytest tools/tests/test_validate_config.py tools/tests/test_generate_item_icons.py tools/tests/test_create_disciple.py -q
backend\.venv\Scripts\python.exe tools/validate_config.py
backend\.venv\Scripts\python.exe tools/check_rng_usage.py
backend\.venv\Scripts\python.exe tools/measure_conquest.py
```

配置检查确认13种材料与全部引用有效，RNG检查通过。工具测试有 pytest-asyncio 默认循环作用域弃用提示，不影响退出状态。后端测试若直接在仓库根运行会因当前包搜索路径报 `ModuleNotFoundError: app`，上述命令明确以 `backend` 为工作目录。

征讨测量结果：[12个固定案例](../../artifacts/sect-conquest/balance-baseline.json)，6胜6负，保存队伍、种子、配置指纹、每轮守备与存活气血。测量只覆盖一级宗门、初期三人阵容，不代表所有阵容或后期平衡已完成。

前端重新导出OpenAPI并生成类型后，在 `frontend` 执行以下检查，退出0：**49项测试通过**，`vue-tsc` 与 Vite 构建通过（111个模块）。

```powershell
node --test tests/game-store.test.mjs tests/sect-management.test.mjs tests/expedition.test.mjs tests/game-text.test.mjs tests/asset-paths.test.mjs tests/battle-playback.test.mjs
npm run build
```

`git diff --check` 通过。构建不能替代人工视觉验收。

集成审查另外修复：第20层战败不得开放下一塔阶；专材缺口导向对应外宗，基础资源缺口按实际值守倾向推荐，不能把无专材产出的本宗值守当成解决入口。

## 人工验收入口

使用独立测试档，避免为观察升级效果修改正式存档。

1. 主殿：查看五座设施的当前收益、下一等级收益和缺口，比较桌面与390px布局、弹窗滚动、键盘焦点。
2. 炼丹/炼器：切换品级、最大可炼、属性丹替换和专武升级；材料不足入口应导向能生产该资源的岗位或外宗。
3. 出征准备：直接选值守/驻守者；一键疗伤能看清库存用量、补炼费用和可治疗人数；出发后原岗位产出暂停。
4. 远行：目标身份刷新不变；每场三人选择、残血、守备和宗主阶段可辨；关闭再开仍保留战役。撤退会说明费用和伤势结果。
5. 战后：攻克奖励不重复领取，驻守最多三人、产出相加；正常回岗和岗位已满两种结果都能理解。

## 兼容与限制

- 存档仍为整档JSON，不改变数据库表结构。旧器具、专武、丹药效果按一级衔接，不重新发放增益和入门资源。
- 已开始的旧十二段远征可继续；新远行必须选宗门。旧塔最高记录20层保留解锁资格，新记录仅按真正通过层数更新。
- 设施首版三级、外宗最多九座；本轮没有扩展入侵、多用户或新的游戏引擎。
- 复用现有角色和敌人美术，没有生成新场景位图。正式界面与新图标的最终观感由用户人工确认。
- 任务开始前已存在的未跟踪截图、临时数据库、工具文字与本地配置目录保持原样，不纳入提交。
