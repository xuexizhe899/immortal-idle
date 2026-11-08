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
"C:/Users/lxz/AppData/Local/Programs/Python/Python311/python.exe" -m venv .venv
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

```bash
bash tools/gen_types.sh
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

## 约束

- 本机不装游戏引擎、不装 Docker Desktop、不装本地生图环境
- Python 依赖只装在项目内 `backend/.venv`，不污染系统环境与其他 venv
- 密钥只放本地 `.env`，不进仓库
