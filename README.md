# 修仙放置 x 休闲肉鸽

自用、非盈利的单机多档放置 roguelite。设计决策见 `DESIGN.md`，任务拆分见 `tasks/`。

## 技术栈

- 前端：Vue 3 + TypeScript + Vite；PixiJS 只做演出，不装游戏引擎
- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Pydantic v2
- 存储：SQLite + aiosqlite（WAL），整档 `state_json` + `revision` CAS
- 部署：Docker Compose（app + Caddy），CI 构建镜像

## 目录

```
config/     静态内容（弟子/词条/配方/敌人/事件/模式/羁绊/风格）
backend/    FastAPI 应用、领域逻辑、仓储、测试
frontend/   Vue 3 界面 + PixiJS 演出
assets/     生图 master 与 manifest
tools/      契约生成、配置校验、资产脚本、备份恢复
deploy/     Dockerfile / compose / Caddyfile
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

输出 `frontend/public/assets/items/<id>.svg` 和清单 `index.json`；总览页在 Vite 启动后访问 `/item-icons.html`。新增道具时，先在 `config/recipes` 或 `config/materials` 添加配置，再在 `tools/generate_item_icons.py` 的 `ART` 中补同名绘图函数，并同步 `frontend/src/components/ItemIcon.vue` 的 ID 列表。重复运行只按内容更新本脚本负责的文件，不清空资产目录。

## 约束

- 本机不装游戏引擎、不装 Docker Desktop、不装本地生图环境
- Python 依赖只装在项目内 `backend/.venv`，不污染系统环境与其他 venv
- 密钥只放本地 `.env`，不进仓库

## 主城与玩法打磨

主城七座建筑分别承载宗门总览、弟子/招贤、值守、爬塔、炼丹、炼器和远征开放状态。存档管理在主殿内；进行中的出征可返回宗门查看，再继续原进度。晨昼暮夜随本地时间变化，也可在“天色”入口预览，不影响服务端收益。

当前战斗按队伍总战力确定结果，PixiJS 只播放真实结果的短演出。人物招式标为资料预览；出发时保存队伍战斗快照，刷新与自然消伤不会改变本局战力。本次完整修改汇总见 `CHANGELOG-2026-11-11.md`，任务记录见 `tasks/T14-frontend-polish.md`。
