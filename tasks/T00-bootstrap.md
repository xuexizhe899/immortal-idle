# T00 · 工程骨架、CI 与契约生成

- 里程碑：M0 ｜ 依赖：无 ｜ 对应文档：DESIGN.md 第 2、3 节

## 目标
搭出可运行的 monorepo 骨架，前后端能各自启动，CI 三个 job 全绿，类型契约可一键再生成。

## 已锁定决策
1. 前端 Vue 3 + TypeScript + Vite；PixiJS 只用于演出，不装任何游戏引擎
2. 后端 Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Pydantic v2，依赖装进项目内 `.venv`
3. 本机已有 Node v22 / npm 10 / corepack / git；不装 Docker Desktop，构建放 CI
4. 契约单一来源：Pydantic → OpenAPI → 生成 TS 类型，生成文件不手改

## 要做的事
1. 按 DESIGN.md 第 3 节建目录树（`config/`、`backend/`、`frontend/`、`assets/`、`tools/`、`deploy/`）
2. 后端：建 `.venv`，装 fastapi、uvicorn、sqlalchemy、aiosqlite、pydantic、alembic、pytest、httpx；写一个 `/api/health` 返回 `{"ok":true}`
3. 前端：`npm create vite`（vue-ts），加 pinia、pixi.js；首页只渲染健康检查结果
4. 写契约生成脚本：导出 `openapi.json` → 生成 `frontend/src/generated/` 下的 TS 类型，并提供 npm script
5. `tools/validate_config.py` 先放空实现（T01 填充），CI 仍要调用它
6. `.github/workflows/ci.yml`：后端 pytest、配置校验、前端构建 + 类型生成，三个 job

## 产出物
- 完整目录树、`backend/pyproject.toml`、`frontend/package.json`、`tools/gen_types.*`、`ci.yml`

## 验收
- [x] `uvicorn` 启动后 `/api/health` 可访问；`vite dev` 经 proxy 取到健康数据（curl 验证通过）
- [x] 修改 Pydantic 字段描述后重生成，`api.d.ts` 同步变化（已实测并回滚）
- [x] push 后 CI 三个 job 全绿（backend / config / frontend 均 success）
- [x] 项目依赖全部在项目目录内（`backend/.venv`），未污染系统 Python 与其他 venv

## 不做
数据库建表、任何 UI 组件、结算逻辑、Docker 镜像、生图脚本。

## 注意
生成目录 `frontend/src/generated/` 加入"勿手改"注释；`.venv`、`node_modules`、`.env` 进 `.gitignore`。

## 执行记录（2026-11-05）
- 根目录即项目根，未额外套 `xiuxian-idle/`；`DESIGN.md`、`tasks/` 与代码同级
- 包管理用 npm（未启用 pnpm）；npm registry 已是 npmmirror，安装未走外网
- TypeScript 由脚手架默认的 6.0.3 降到 5.9.3：`openapi-typescript@7` 的 peer 要求是 `typescript ^5.x`。降级比 `--legacy-peer-deps` 干净，CI 的 `npm ci` 不会冲突
- 契约链路：`backend/scripts/export_openapi.py` → `backend/openapi.json`（gitignored）→ `openapi-typescript` → `frontend/src/generated/api.d.ts`（gitignored）；`bash tools/gen_types.sh` 一键重生成
- 实测：pytest 2 passed；validate_config ok；vite build 成功（67.67 kB / gzip 26.97 kB）；`curl http://127.0.0.1:5173/api/health` 经 Vite proxy 返回 `{"ok":true,...}`
- 版本：fastapi 0.162.0 / sqlalchemy 2.1.8 / pydantic 2.14.2；vue 3.5.44 / vite 8.3.6 / pinia 4.1.0 / pixi.js 8.22.0 / openapi-typescript 7.13.0
- 已 `git init`（main）但未做首次提交；`.workbuddy/`、`.venv/`、`node_modules/`、`openapi.json`、`src/generated/` 均已忽略
- 待办：推送到 GitHub 验证 CI 三个 job；首次 commit 交给用户执行
