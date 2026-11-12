# 2026-11-12 修改汇总：前端资源引用与展示层整理

本次只落实前端分层：统一资源解析、拆分展示函数、按职责归位组件。未改玩法、存档结构、接口契约、业务 ID 或资产目录，未调用生图 API，未新增位图。

## 已完成

### 1. 统一资源引用

- 新增 `frontend/src/presentation/assetPaths.ts`：
  - `characterImage`：人物资源键转本地 PNG，站内 URL 原样返回，自带扩展名时不重复拼接。
  - `discipleImage`：宗门、图鉴按当前 catalog 的 `asset_id` 取立绘。
  - `snapshotDiscipleImage`：出征优先使用固定快照的 `asset_id`，仅旧档缺字段时回退当前 catalog。
  - `sceneImage`：场景字段兼容 `/assets/...png` 站内 URL 与不带前导斜杠的资源键。
  - `itemIconPath`：沿用 18 个允许道具 ID；未知、空值或含路径片段的 ID 返回空串，由组件显示本地占位。
  - `TOWER_SCENE_IMAGE`、`TOWER_SPRITE_IMAGE`：集中塔战场景与准备页塔图地址。
- `gameDisplay.ts`、`BattleStage.vue`、`RunView.vue`、`itemIcons.ts` 中重复的路径拼接与道具映射已移除。
- `CityView` 主城背景、建筑 sprite 与 `PreparePanel` 塔图改走统一入口；`BattleStage` 场景与战报人物也统一解析。
- 图片加载失败反馈保持原样：道具显示本地 SVG 占位，战场人物回退程序轮廓，主城 sprite 隐藏。

### 2. 展示函数拆分

| 模块 | 职责 |
|---|---|
| `frontend/src/shared/format.ts` | `number` 纯数值格式化，不依赖游戏类型 |
| `frontend/src/presentation/gameText.ts` | 弟子流派、属性、稀有度、效果、伤势与资源名称等游戏文案映射 |
| `frontend/src/presentation/assetPaths.ts` | 人物、场景与道具的本地资源解析 |

`frontend/src/components/gameDisplay.ts` 已删除，所有调用点改为从 shared / presentation 明确导入。仅单组件使用的敌我状态文案、技能目标与条件等私有映射仍就近保留。

### 3. 组件归属

| 目录 | 迁入组件 |
|---|---|
| `frontend/src/components/ui/` | `GameIcon.vue`、`NoticeBubble.vue`、`PanelModal.vue` |
| `frontend/src/components/game/` | `DiscipleCard.vue`、`PartyStrip.vue`、`SkillDetails.vue`、`ItemIcon.vue`、`CityDock.vue`、`CityNavIcon.vue` |
| `frontend/src/rendering/` | `BattleStage.vue`、`battlePlayback.ts`、`SkillVfx.vue`、`EnemyFigure.vue`、`CityAtmosphere.vue`、`dayCycle.ts` |

通用 UI 不读取游戏 store；`PartyStrip.vue` 保留原有阵容状态连接职责；战报播放、技能特效、敌人轮廓、昼夜视觉及其计时器全部归入 rendering。全部导入、测试与测试夹具路径已同步，依赖方向无环。

### 4. 测试与说明

- `frontend/tests/item-icons.test.mjs` 更新并重命名为 `frontend/tests/asset-paths.test.mjs`，保留道具清单覆盖与未知 ID 占位测试，新增：
  - 人物资源键、自带扩展名键与站内 URL 的解析及真实文件存在性。
  - 场景站内 URL 与资源键解析。
  - 固定出征快照优先于当前 catalog 的立绘选择。
- `frontend/tests/battle-playback.test.mjs` 更新为 rendering 路径。
- 同步更新 `README.md` 道具 ID 同步位置、`ARCHITECTURE.md` 目录状态与剩余差距表、`DESIGN.md` 前端目录说明。

## 本次验证（实际执行）

以下命令在本次交付代码上执行，退出状态均为 0：

| 命令 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe -m pytest backend/tests -q` | 118 passed |
| `backend\.venv\Scripts\python.exe -m pytest tools/tests -q` | 102 passed |
| `backend\.venv\Scripts\python.exe tools/validate_config.py` | 配置校验通过：32 技能、16 人、5 羁绊 |
| `backend\.venv\Scripts\python.exe tools/check_rng_usage.py` | RNG 使用检查通过 |
| `backend\.venv\Scripts\python.exe backend/scripts/export_openapi.py` | 契约导出成功 |
| `npm run gen:api`（frontend） | 前端类型生成成功 |
| `npm test`（frontend） | 15 passed |
| `npm run build`（frontend） | 类型检查与生产构建通过；JS 175.76kB / gzip 64.45kB，CSS 60.09kB / gzip 13.00kB |

后端存在一条既有 Starlette/httpx 弃用警告，工具测试存在既有 pytest-asyncio 配置提示；本次未修改技术栈。

## 未执行与待办

- 按用户最新指令，本次未进行浏览器实际渲染、桌面 / 390px 截图及主城昼夜、弟子卡、编队、弹窗、战斗重播、缺图、等待、错误和减少动态效果的视觉检查。本次没有视觉证据，不宣称视觉已验收，需由用户人工测试确认。
- `ARCHITECTURE.md` 第 8 节其余存量差距仍待单独任务处理：`SaveSlotsPanel` 直接调用 `api.exportSave`、路由从 `api/saves.py` 取 `get_repo`、`SaveRepository.create_slot` 生成新档、`run_engine` 缺省加载配置与种子。
- 后端编排、存档导出 API、生图脚本、公共风格模板、参考图编辑与战斗数值平衡不在本次范围。

## 交付边界

仅提交并推送本任务的前端分层、测试与直接相关说明。未部署，未变更真实服务器，未改写用户真实存档；`AGENTS.md` 中已有的本地未提交修改未纳入本次提交。