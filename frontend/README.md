# 前端目录导航

本目录是修仙放置游戏的 Vue 3 + TypeScript + Vite 前端，Pinia 组织客户端状态。玩法结算由后端负责，当前战斗演出使用 Vue、SVG 与 CSS；`package.json` 中保留的 PixiJS 依赖不代表当前战场使用 PixiJS。

开始修改前阅读仓库根目录的 [AGENTS.md](../AGENTS.md) 和 [ARCHITECTURE.md](../ARCHITECTURE.md)。人物、场景及资产制作另见 [ART_DIRECTION.md](../ART_DIRECTION.md)。本页帮助定位文件，不替代这些规范。

## 1. 顶层目录

```text
frontend/
├─ src/                 应用源码、契约类型与界面素材
├─ public/              按原路径提供的静态资源、资产检查页
├─ tests/               Node 测试与隔离的 store 测试支架
├─ .vscode/             编辑器扩展建议
├─ node_modules/        npm 安装的依赖及工具缓存，不是业务源码
├─ dist/                Vite 生产构建输出，不手改
├─ index.html           单页应用入口，引用 src/main.ts
├─ package.json         依赖声明与 npm 命令
├─ package-lock.json    npm 锁定依赖版本的生成文件
├─ vite.config.ts       Vue 插件、@ 别名、开发服务与 API 代理
├─ tsconfig*.json       应用、工具配置文件的 TypeScript 检查设置
└─ .gitignore           依赖、构建、日志及本机配置的忽略规则
```

当前没有 `frontend/scripts/` 目录。前端命令定义在 `package.json` 的 `scripts` 中；配置校验、资产制作及接口导出脚本位于仓库根目录的 `tools/`、`backend/scripts/`，不要为了放命令新建一份重复脚本目录。

## 2. `src/`：源码归属

| 位置 | 放什么、从哪里开始看 |
|---|---|
| `main.ts` | 创建 Vue 应用并安装 Pinia，载入全局样式。 |
| `App.vue` | 组装主城、出征视图和全局消息气泡，管理顶层页面切换。 |
| `style.css` | 全局主题变量、基础排版、按钮和复用样式。页面布局、局部演出样式优先留在所属组件。 |
| `views/` | 页面与功能面板，连接 store 并组织操作。`CityView.vue` 是主城，`RunView.vue` 是出征，`ConquestRun.vue` 通过真实战报承载宗门擂台；`CodexPanel.vue`、`PreparePanel.vue`、`DutyPanel.vue`、`CraftPanel.vue` 分别承载弟子、出征准备、值守、炼制；宗门与存档入口见 `SectPanel.vue`、`SaveSlotsPanel.vue`。 |
| `stores/` | `game.ts` 保存服务端响应镜像、revision、当前选择和本地偏好，串联命令、并发锁及操作反馈。页面通过 action 请求变更，不能直接改资源、伤势或出征结果。 |
| `api/` | `client.ts` 负责 HTTP 传输、超时、错误及契约类型别名。它不依赖 store 或组件，不决定伤害、培养费用和挂机收益。 |
| `generated/` | `api.d.ts` 是从后端 OpenAPI 生成的类型，禁止手改。类型源头是后端 Pydantic，不能在页面再手写一套同构 DTO。 |
| `components/` | 只按 `ui/` 与 `game/` 放组件，具体职责见下表；不要继续新增平铺组件。 |
| `presentation/` | 纯展示转换。`gameText.ts` 处理游戏名词和效果说明；`assetPaths.ts` 统一将人物资源键、场景路径、物品和敌人 ID 解析为本地资源 URL。不得请求接口、读 store、操作 DOM 或重算游戏结果。 |
| `rendering/` | 视觉生命周期和演出。`BattleStage.vue`、`battlePlayback.ts` 播放真实战报；`EnemyFigure.vue`、`SkillVfx.vue` 表现敌人和技能；`CityAtmosphere.vue`、`dayCycle.ts` 处理主城环境。计时器和监听器在这一层释放，播放游标不作为游戏进度。 |
| `shared/` | 无游戏业务含义的基础函数，当前为 `format.ts` 数值格式化；只依赖标准库，不依赖 Vue、游戏类型、store 或浏览器存储。 |
| `assets/` | 由 Vite import 管理的界面素材。当前仍有 `vue.svg`、`vite.svg`、`hero.png` 等脚手架遗留文件，不是人物立绘或主城素材的正式目录，不因整理文档而删除。 |

### `src/components/` 的两个子目录

| 目录 | 内容与边界 |
|---|---|
| `ui/` | `PanelModal.vue`、`NoticeBubble.vue`、`GameIcon.vue`：弹窗、消息反馈、通用图标。使用 props/emits，不认识弟子、存档或战斗规则。 |
| `game/` | `CityDock.vue`、`CityNavIcon.vue`、`DiscipleCard.vue`、`DiscipleTraining.vue`、`PartyStrip.vue`、`ItemIcon.vue`、`SkillDetails.vue`：游戏业务展示与交互。默认 props 输入、emits 输出；明确连接共享状态的组件（如编队条）才读取 store。 |

设施经营由 `components/game/FacilitiesSection.vue` 嵌入主殿，队伍补炼疗伤由 `PartyHealing.vue` 在问道和远行整备中复用；预览、消耗和收益以服务端响应为准。`ExpeditionPanel.vue` 展示固定外宗目标与最多三人的驻守编制，`CraftPanel.vue` 使用真实配方预览实现批量、品级与升级，不在客户端模拟扣料。

常见修改入口：培养展示先看 `DiscipleTraining.vue` 和 `CodexPanel.vue`；培养规则、费用和预览真值在后端。物品图片先看 `ItemIcon.vue` 与 `assetPaths.ts`；真实物品效果在后端。战斗节奏和特效看 `rendering/`，胜负与每次行动来自后端战报。

### 状态、展示、演出的分工

```text
页面事件 → store action → api/client → 后端命令
                                ↓
页面 / 业务组件 ← store 接收完整响应快照与 revision
        ↓
presentation（文案、资源） / rendering（播放、特效）
```

后端是资源、成长、伤势与出征结果的权威。前端可以暂停、跳过、重播演出，不能补造伤害或再次结算。请求结果不确定时查询最新状态，不能自动重发可能扣费的命令。进行中的出征优先读取本局快照，不能拿最新 catalog 覆盖已固化输入。

## 3. `public/`：静态资源与检查入口

`public/` 的文件由 Vite 原样提供：例如 `public/assets/items/han_tie.svg` 对应 `/assets/items/han_tie.svg`，不带 `/public` 前缀。这里的文件不通过业务模块 import，也不能依靠文件存在就认定玩法已开放。

| 位置 | 用途与当前状态 |
|---|---|
| `favicon.svg` | 浏览器标签页图标，由 `index.html` 引用。 |
| `icons.svg` | 本地 SVG 图标资源。 |
| `item-icons.html` | 18 种基础物品图标的独立检查页，用于查看轮廓、小尺寸及背景对比，不是玩家功能页。 |
| `art-foundation.html` | 精修物品、关羽专武外观概念和敌人形象的独立美术审阅页；用于人工审阅外观。T19/T20 的玩法实现另行验证，不以审阅页代替。 |
| `assets/` | 游戏运行可访问的图片与 SVG。分组如下，来源/master 和生成记录仍在仓库根目录 `assets/`。 |

### `public/assets/` 的实际分组

| 目录 | 内容与使用方式 |
|---|---|
| `trial-v03/` | 当前 16 名人物主用立绘及 `scene_tower_trial.png` 塔内背景。人物 `asset_id` 通常形如 `trial-v03/guanyu`，由资源解析补齐扩展名。 |
| `city-v03/` | 当前七建筑主城整图 `scene_city_complete.png`，背景引用来自 `config/ui/city.json`。 |
| `items/` | 基础 18 张材料、丹药、法器 SVG 与 `index.json`。由 `tools/generate_item_icons.py` 生成，新增正式 ID 时同步配置、生成源码、清单及前端注册表，避免只放一张图。 |
| `buildings/` | 独立建筑 PNG。当前出征准备仍通过 `TOWER_SPRITE_IMAGE` 使用 `sprite_tower.png`；整图主城使用 `city-v03/`。不能因为目录较早就整体视为无用。 |
| `scenes/` | 早期 `city_terrain.png` 地形素材，当前主城入口已使用整图；后续清理前仍须查配置、代码与工具引用。 |
| `backup_pixel_v0/` | 历史人物像素资源备份，不作为新增人物的当前风格基准。 |
| `assets/` 根目录中的人物 PNG | 历史根路径立绘，资源解析仍保留按模板 ID 回退的路径；正式人物优先使用 catalog 中的版本化 `asset_id`。 |
| `art-foundation/items/` | 四件代表物品的精修 SVG，每件有小图和 `_display.svg` 展示图。前三件既有物品通过 `itemArtworkPath` 使用；关羽专武仅为外观概念，不加入正式可用物品 ID。源码是 `tools/generate_art_foundation_items.py`。 |
| `art-foundation/enemies/` | 10 种敌人透明 PNG 与 `index.json`。石甲灵卫、流云弓卫、玉衡守将、问道真灵有现有敌人定义；其余六种是美术储备。`enemyImage` 登记图片不等于服务端已安排遭遇或实现技能。 |
| `art-foundation/sects/` | 外宗 13 名弟子和 3 位宗主的透明 PNG，高 512px。`config/sects.json` 按流派指定图片键，预览与战斗优先读取服务端快照的 `asset_id`；空键继续回退旧敌图。原图、提示词及人工审阅材料在根目录 `assets/masters/sect-conquest/`、`assets/prompts/` 与 `artifacts/sect-conquest/`。 |
| `art-foundation/enemies/scenes/` | 当前为空的预留子目录，没有已接入的新场景；不把它列作现有场景能力。 |

页面和组件经 `presentation/assetPaths.ts` 获取路径，避免各处拼版本目录。运行时只读本地正式资源，不请求生图 API，不加载 master 或全部历史资产。图片失败回退由显示组件处理；回退图片不改变战果和物品效果。

## 4. `tests/` 与命令位置

当前使用 Node 内置测试运行器；测试读取 TypeScript 源码并转译后检查公开行为，没有单独的前端测试构建目录。

| 文件 | 关注范围 |
|---|---|
| `game-store.test.mjs` | store 命令、状态同步、并发和失败恢复等行为。 |
| `store-harness.mjs` | 加载实际 client/store、构造隔离响应和模拟输入的测试支架，不是正式游戏数据。 |
| `asset-paths.test.mjs` | 资源键解析、物品注册表、固定出征图片与本地文件对应关系。 |
| `battle-playback.test.mjs` | 战报事件选择、播放状态还原及相关展示行为。 |

玩法算法、保存与接口回归位于 `backend/tests/`；资产生成与内容校验测试位于 `tools/tests/`。不要在前端测试里复制服务端伤害或收益算法。

以下命令从 `frontend/` 执行，按当前任务范围和根目录执行约束选择，不因查看本页而自动运行：

```powershell
npm ci                 # 按 lockfile 安装依赖
npm run dev            # 开发服务；当前配置端口 5173
npm run gen:api        # 从 ../backend/openapi.json 生成 src/generated/api.d.ts
npm test               # Node 测试
npm run build          # vue-tsc -b 类型检查，再执行 Vite 生产构建
npm run preview        # 本地查看已有 dist，不能替代构建
```

`vite.config.ts` 将 `/api` 代理到 `http://127.0.0.1:8000`，需要另行启动后端。接口契约变动时先在仓库根目录运行 `backend\.venv\Scripts\python.exe backend/scripts/export_openapi.py`，再进入本目录运行 `npm run gen:api`；不要直接编辑生成类型绕过契约管线。

## 5. 依赖、缓存与本机文件

- `.vscode/` 当前保存 `extensions.json` 的 Vue 编辑器扩展建议，不是运行配置。
- `node_modules/` 是 npm 安装结果；其中 `.bin/` 是命令入口，`.vite/`、`.vite-temp/`、`.tmp/`、`.typescript-*` 等是工具预构建、临时配置或编译缓存。具体子目录随工具版本变化，不手改、不提交，不当作源码归属。
- `dist/` 及其 `assets/` 是生产构建产物，包括打包代码和复制的 public 资源；修复源文件后重新构建，不直接修补 dist。目录存在不代表当前源码已通过构建或已部署。
- `dev.log`、其他日志、`*.local` 等本机文件按 `.gitignore` 处理，不能把本地地址、日志或缓存当作共享项目配置。
- `package-lock.json` 应由 npm 更新并与依赖声明一起审查；它不同于禁止手改的 API 契约，但也不应通过手工改锁定条目掩盖依赖变化。
