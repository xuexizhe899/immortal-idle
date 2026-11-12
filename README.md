# 修仙放置 x 休闲肉鸽

自用、非盈利的单机多档放置 roguelite。玩法决策见 [DESIGN.md](DESIGN.md)，分层、目录与资产引用规范见 [ARCHITECTURE.md](ARCHITECTURE.md)，任务拆分见 `tasks/`。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite + Pinia；当前演出使用 Vue / SVG / CSS，PixiJS 仅保留为可选演出依赖
- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Pydantic v2
- 存储：SQLite + aiosqlite（WAL），整档 `state_json` + `revision` CAS
- 部署规划：Docker Compose（app + Caddy）；部署文件与镜像流水线尚未落地

## 目录

```
config/     静态内容、技能与羁绊、主城布局、风格约定
backend/    FastAPI 应用、领域逻辑、仓储、测试
frontend/   Vue 3 界面、SVG 演出、本地运行资产
assets/     素材来源、master、提示与生成记录
tools/      契约辅助、配置校验、资产与内容脚本、离线测量
artifacts/  任务草稿、截图、测量与验收证据
docs/       方案与审查记录
tasks/      任务卡与验收清单
```

## 本地启动

后端（首次）：

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

前端（首次）：

```bash
cd frontend
npm install
npm run dev
```

**首次启动前端前必须先生成一次接口类型**，否则 `src/generated/` 为空：

```powershell
cd backend
.venv/Scripts/python.exe scripts/export_openapi.py
cd ../frontend
npm run gen:api
```

## 常用命令

| 目的 | 命令 |
|---|---|
| 重新生成接口类型 | `bash tools/gen_types.sh` |
| 数据库迁移 | `cd backend && .venv/Scripts/python.exe -m alembic upgrade head` |
| 处理立绘资产 | `backend/.venv/Scripts/python.exe tools/normalize_assets.py` |
| 校验配置引用 | `python tools/validate_config.py` |
| 后端测试 | `cd backend && .venv/Scripts/python.exe -m pytest -q` |
| 前端构建 | `cd frontend && npm run build` |

`backend/openapi.json` 与 `frontend/src/generated/` 都是构建产物，已被 gitignore，不要手改。

## 道具图标

丹药、法器与材料图标由本地脚本绘制，不走生图 API：

```powershell
backend\.venv\Scripts\python.exe tools\generate_item_icons.py
```

开发时可用 `--only qing_feng_jian` 单独更新图标；已有完整输出目录的清单会保留其余道具，新的预览目录只登记实际生成的文件。

输出 `frontend/public/assets/items/<id>.svg` 和清单 `index.json`；总览页在 Vite 启动后访问 `/item-icons.html`。新增道具时，先在 `config/recipes` 或 `config/materials` 添加配置，再在 `tools/generate_item_icons.py` 的 `ART` 中补同名绘图函数，并同步 `frontend/src/components/itemIcons.ts` 的 ID 列表。重复运行只按内容更新本脚本负责的文件，不清空资产目录。

## 约束

- 本机不装游戏引擎、不装 Docker Desktop、不装本地生图环境
- Python 依赖只装在项目内 `backend/.venv`，不污染系统环境与其他 venv
- 密钥只放本地 `.env`，不进仓库

## 主城与玩法打磨

主城七座建筑分别承载宗门总览、弟子/招贤、值守、爬塔、炼丹、炼器和远征开放状态。存档管理在主殿内；进行中的出征可返回宗门查看，再继续原进度。晨昼暮夜随本地时间变化，也可在“天色”入口预览，不影响服务端收益。

首页采用一屏主城与底部固定功能栏，提供宗门、弟子、值守、炼丹、炼器、问道六入口，与建筑打开相同面板。问道入口按真实出征状态显示“继续出征”或“待结算”；未开放码头只保留地图入口。当前目标以可点击浮签显示，右下可收取收益；收益与最近出征明细在宗门总览查看，阵容在弟子与出征准备中调整。手机地图可在场景区域左右滑动，底栏始终可达；底栏图标由本地 SVG 绘制。

T16 已将原型总战力判定升级为 1–6 人自动战斗：逐人气血跨层保留，主动、被动和羁绊由服务端执行，前端只播放真实战报。出发时固化角色、技能、羁绊、敌人、模式及词条定义，刷新与自然消伤不会改变本局输入。项目尚未上线，本期不保留旧出征结构兼容，也不自动删除本地数据；开发与验收请使用独立新档。本期修改与检查结果见 [修改汇总](CHANGELOG-2026-11-12.md)，此前主城修改见 `CHANGELOG-2026-11-11.md`。

规则与验收清单见 [T16 六人出征、技能与羁绊组合](tasks/T16-skills-and-bonds.md)。技能通过伤害、降防、治疗和护盾形成跨角色配合；五虎、封神、奔月、三分天下强化特定成员技能，诗圣继续用于值守。战斗最多 20 轮，只有节点与词条决策消耗既有确定性随机源，战报重播与跳过演出都不重新结算。

## 程序美术与加载

人物使用现有立绘，复杂场景使用本地背景；敌人轮廓、技能特效、护盾和状态提示用 SVG 与 CSS 在运行时绘制。几何形状、配色和运动参数可以组合出不同演出，新增技能通常只需选择特效参数，不为每种效果新增位图。源组件保留完整绘图逻辑，不调用运行时生图接口。

当前角色只加载参战图片，非首屏人物列表延迟加载。现有 16 张主用立绘与塔场景约 3.17 MiB；本期复用这些资产，未新增生图资产。复杂新场景后续可继续沿用云端模型及本地 master 管线，单次任务生成上限为 100 张；实际是否生图按场景需要判断。

## 角色内容草稿

`tools/create_disciple.py` 可从角色卡生成弟子、技能、可选羁绊、立绘提示和数值报告；默认只生成草稿，显式 `--apply` 才写正式配置。使用步骤和孙悟空示例见 [T15 角色快速创建与数值平衡](tasks/T15-character-creation.md)。
