# 后端目录导航

本目录保存游戏规则、HTTP 接口、存档持久化和数据库迁移。后端采用 Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2.0 async 与 aiosqlite；资源、战斗、培养、挂机收益等结果由服务端计算。

本文按当前工作区目录说明代码放在哪里、从哪里开始修改；包含尚未提交的模块，不代表这些模块已经测试或发布。运行准备见[项目 README](../README.md)，分层与依赖约束见 [ARCHITECTURE.md](../ARCHITECTURE.md)，执行、验证与数据保护规则见 [AGENTS.md](../AGENTS.md)。

## 1. 目录总览

```text
backend/
├─ app/                       # 应用源码
│  ├─ api/                    # HTTP 接口与当前命令编排
│  ├─ domain/                 # 战斗、培养、值守、炼制等游戏规则
│  ├─ models/                 # Pydantic 状态、配置与接口结构
│  ├─ repositories/           # 整档持久化、CAS、快照与 SQL 表定义
│  ├─ main.py                 # FastAPI 应用、生命周期和路由注册
│  ├─ db.py                   # 数据库引擎、WAL 与异步会话工厂
│  └─ config_loader.py        # 读取仓库根目录 config/，进程内缓存
├─ alembic/                   # 数据库结构迁移源码
│  ├─ versions/               # 按版本排列的升级/降级脚本
│  └─ env.py                  # 迁移环境和表元数据接入
├─ scripts/                   # 后端开发辅助脚本
│  └─ export_openapi.py       # 从当前 FastAPI 应用导出接口契约
├─ tests/                     # 领域、API、持久化与存档回归测试
├─ data/                      # 本地 SQLite 数据，已忽略，不是源码
├─ .venv/                     # 项目专用 Python 依赖环境，已忽略
├─ app.py                     # 本地开发启动脚本，与 app/ 包用途不同
├─ alembic.ini                # 迁移路径及数据库连接配置
├─ pyproject.toml             # Python 项目、依赖和 pytest 配置
└─ openapi.json               # 自动导出的接口契约，已忽略，禁止手改
```

各包的 `__init__.py` 用于 Python 包组织。运行后可能在多个目录出现 `__pycache__/`，它们是解释器缓存，不属于业务模块。

## 2. app/：业务源码

### api/：接收请求、组织命令、返回快照

路由负责 HTTP 参数校验、依赖获取、业务错误到 HTTP 错误的映射，以及当前规模下的一次操作编排。领域计算交给 `domain/`，保存交给 `repositories/`。

| 文件 | 主要职责 |
|---|---|
| `health.py` | 存活检查接口。 |
| `catalog.py` | 向前端提供弟子、技能、羁绊、配方等当前配置资料。 |
| `saves.py` | 多存档管理、读取、导入导出、复制、快照与恢复；当前也提供仓储依赖 `get_repo`。 |
| `state.py` | 共享命令边界：校验 revision、补算旧区间、原子提交、组装游戏快照。它是编排辅助模块，不是单独的业务路由。 |
| `settle.py` | 挂机收益结算接口。 |
| `duty.py` | 值守名单查询、上岗与下岗。 |
| `recruit.py` | 招募命令入口。 |
| `disciples.py` | 培养预览、升级、突破与疗伤入口。 |
| `craft.py` | 炼制命令入口，接收配方与必要的目标弟子。 |
| `items.py` | 指定弟子服用丹药的命令入口。 |
| `weapons.py` | 专属武器列表、锻造、装备与卸下入口。 |
| `run.py` | 出征查询、塔阶/宗门出发、问道选路与道法、三人擂台、撤退和结算。 |
| `facilities.py` | 设施升级成本与收益预览、升级命令。 |
| `garrison.py` | 外宗驻守调岗，先补算旧收益、再一次保存新编制。 |

新增消耗命令优先复用 `state.py` 的 `prepare_mutation` / `commit_mutation` 流程，避免漏掉旧区间收益或绕过 CAS。路由之间不要通过调用另一路由函数来完成业务。

### domain/：可解释、可重放的游戏规则

这里接收内存状态、配置和必要的时间/随机输入，执行规则并返回结果；不负责 HTTP、数据库连接或事务提交。

| 文件 | 主要职责 |
|---|---|
| `battle.py` | 有限回合自动战斗、目标选择、技能、状态、护盾、治疗及真实逐行动战报。 |
| `run_engine.py` | 出征状态流转、固定参战快照、敌人编成、节点推进、战利品与出征结算；调用战斗模块。 |
| `affix.py` | 词条协同组、权重和候选抽取。 |
| `rng.py` | 既有种子随机源及游标；局内玩法随机使用它保证重放。 |
| `progression.py` | 新档入门状态、升级费用、等级/境界边界、突破及出征锁定校验。 |
| `training.py` | 培养只读预览，复用实际战斗属性、培养费用和值守规则，不扣资源。 |
| `recruit.py` | 弟子招募与已拥有角色的招募处理。 |
| `craft.py` | 配方材料消耗、炼制效果与特殊配方规则。 |
| `items.py` | 丹药库存、物品 ID 归一、指定弟子服用与消耗规则。 |
| `weapons.py` | 专武获取条件、唯一归属、装备槽与个人属性加成。 |
| `duty.py` | 值守倾向、生产专长、外宗驻守产出与速率事件记录。 |
| `facilities.py` | 三级设施成长上限、升级费用及器具/丹药品级倍率。 |
| `conquest.py` | 确定性外宗生成、擂台守备、宗主战与撤退规则。 |
| `deployment.py` | 出征自动离岗/回岗、外宗驻守及岗位冲突处理。 |
| `settle.py` | 按服务端时间和速率变更分段补算挂机收益。 |
| `injuries.py` | 伤势、自然恢复、治疗与战斗攻击折扣。 |

静态内容在仓库根目录 [`config/`](../config/)，不是这个目录中的第二份配置。新技能、敌人或配方先检查现有模型和规则能否表达；不要为每个内容 ID 单独复制战斗流程。

### models/：数据结构与契约来源

| 文件 | 主要职责 |
|---|---|
| `base.py` | 项目共用 Pydantic 契约基类，统一输入默认值与输出 schema 行为。 |
| `save.py` | 整档 `GameState`、弟子、出征、战报摘要、槽位元数据和导入导出结构。 |
| `battle.py` | 技能动作、羁绊、参战单位、临时状态、敌人定义与行动事件。 |
| `api.py` | 游戏快照、命令响应、catalog 与培养预览等接口结构。 |

模型校验数据结构，不查询数据库、不加载配置、不自行结算游戏。仅一个路由使用的简单请求体也可能就近定义在 `api/`；不必为了目录整齐复制等价 DTO。

### repositories/：保存与恢复整档状态

| 文件 | 主要职责 |
|---|---|
| `tables.py` | SQLAlchemy Core 表与 `metadata`；当前主要是存档槽和存档快照表。 |
| `saves.py` | `SaveRepository`：整档 JSON 读写、revision CAS、槽位元数据、复制/导入导出、快照及序列化版本处理。 |

游戏状态保存在一份 `state_json` 中。仓储负责可靠保存已计算的结果，不负责战斗和收益规则；状态与结算时间锚点通过同一次 CAS 保存。当前存量依赖偏差及后续归位要求见 `ARCHITECTURE.md` 第 8 节。

### app/ 根目录模块

- `main.py` 创建 FastAPI 应用、注册 `/api` 路由，并在生命周期中创建/释放数据库引擎和会话工厂。
- `db.py` 使用异步 SQLite 连接，并启用 WAL 和外键约束。默认数据库位于 `backend/data/xiuxian.db`；应用可通过 `XIUXIAN_DB_URL` 指定独立连接。
- `config_loader.py` 从仓库根目录 `config/` 加载 JSON，并缓存读取结果。新增配置种类需要核对加载入口、catalog、模型和仓库根目录的配置校验工具，不能仅增加文件便视为已接入。

## 3. alembic/：数据库结构演进

- `env.py` 连接 Alembic 与 `app/repositories/tables.py` 的元数据，支持离线 SQL 和在线迁移。
- `versions/` 存放有版本关系的迁移脚本；当前 `0001_init.py` 创建存档槽与快照表。
- 根级 `alembic.ini` 设置 `script_location` 和同步迁移连接；应用的 `XIUXIAN_DB_URL` 不会自动替代这个文件中的迁移 URL。

修改数据库表结构时同时核对表定义和迁移。修改整档 JSON 字段时先评估 Pydantic 默认值、schema 版本与仓储转换，不把每个 JSON 字段都当作新表列。迁移升降验证只能使用隔离数据库，不能对真实存档执行破坏性降级。

## 4. scripts/ 与接口生成产物

当前 `scripts/export_openapi.py` 导入 `app.main:app`，将当前 Pydantic/FastAPI 契约写为 `backend/openapi.json`。前端再从该文件生成 TypeScript 类型：

```text
models/ 与路由输入输出
    → scripts/export_openapi.py
    → backend/openapi.json
    → frontend 的 npm run gen:api
    → frontend/src/generated/api.d.ts
```

`openapi.json` 和 `frontend/src/generated/` 都是可重新生成的产物，已由 Git 忽略，不能手改。需要改变字段时先修改源模型及对应行为。契约生成与检查命令见根目录 `AGENTS.md`；本导航不表示这些命令已执行。

## 5. tests/：按职责定位回归

测试文件当前直接放在 `tests/`，没有另设 API 或领域子目录。

| 关注范围 | 对应文件 |
|---|---|
| 战斗与羁绊 | `test_battle.py`、`test_bonds.py` |
| 出征、种子和固定快照 | `test_run_engine.py`、`test_run_party_snapshot.py`、`test_rng.py` |
| 培养、招募与生产 | `test_production_progression.py`、`test_recruit.py`、`test_duty.py` |
| 炼制与伤势 | `test_craft.py`、`test_injuries.py` |
| 丹药使用与专武 | `test_items.py`、`test_weapons.py` |
| 时间与挂机补算 | `test_settle.py` |
| HTTP 与命令串联 | `test_gameplay_api.py`、`test_health.py` |
| 存档可靠性与契约 | `test_saves.py`、`test_serialization_schema.py` |

测试使用隔离数据库或内存状态，不能借用 `data/` 下的真实存档。内容/美术工具测试在仓库根目录 `tools/tests/`，前端测试在 `frontend/tests/`，不放入本目录。

## 6. 本地环境、数据和缓存

| 路径 | 性质与使用约定 |
|---|---|
| `data/` | 本地运行数据，默认包含 SQLite 数据库，运行时也可能出现 `-wal`、`-shm` 文件；整目录已忽略，不是测试夹具或可随意清理的缓存。 |
| `.venv/` | 项目专用虚拟环境；Python 依赖只装在这里，不修改系统 Python 环境。 |
| `.venv/Scripts/` | Windows 下的解释器、包管理器和已安装命令入口。 |
| `.venv/Lib/` | 虚拟环境安装的第三方依赖；不要把修改业务代码写入依赖目录。 |
| `.venv/Include/` | 虚拟环境的头文件支持目录，由 Python/包安装过程维护。 |
| 各处 `__pycache__/`、`*.pyc` | Python 自动生成的字节码缓存，已忽略。 |
| `.pytest_cache/`、`.ruff_cache/`、`*.egg-info/`（如出现） | 测试、检查或安装过程生成的本地缓存/元数据，已忽略，不属于游戏数据。当前 pytest 配置禁用自身缓存提供器。 |

不读取或提交本地密钥、真实数据库、依赖目录或缓存。目录被 Git 忽略不代表其中的数据已获删除授权。

根级 `app.py` 是开发启动脚本：在 `backend` 工作目录下使用本项目解释器执行，启动 `app.main:app`，仅监视 `app/` 和仓库根目录 `config/` 的热重载。它不等同于数据库迁移脚本。

## 7. 依赖流与常见改动入口

```text
app/main.py → api/（HTTP + 命令编排）
                 ├─ domain/ → models/
                 ├─ config_loader.py → 仓库根目录 config/
                 └─ repositories/ → models/ + tables.py → 数据库
app/main.py → db.py（引擎与会话工厂）
```

这表示目标依赖方向；当前已知存量偏差按根目录架构规范处理。不要让 `domain/` 查询数据库、让仓储决定游戏胜负，或在前端复制一套结算逻辑。

| 要修改什么 | 从哪里入手 |
|---|---|
| 技能效果、目标、护盾、治疗或行动事件 | `domain/battle.py`、`models/battle.py`；配合 `config/skills/`、`config/bonds/` 和相关回归。 |
| 出征、敌人编成、跨层气血或奖励结算 | `domain/run_engine.py`、`api/run.py`、`models/save.py`；内容核对 `config/enemies/`、`config/modes/`。 |
| 培养费用、门槛与预览 | `domain/progression.py`、`domain/training.py`、`api/disciples.py`，并核对炼制与招募入口。 |
| 值守与离线收益 | `domain/duty.py`、`domain/settle.py`、`api/state.py` 及对应路由；关注补算和速率变更锚点。 |
| 炼制或物品效果 | `domain/craft.py`、`api/craft.py`、`config/recipes/`；涉及个人状态再核对 `models/save.py`。 |
| 指向性服药或专武装备 | `domain/items.py`、`domain/weapons.py`、对应 API 及 `config/recipes/`、`config/weapons/`。 |
| 接口字段 | Pydantic 源模型、路由输入输出，之后重新生成契约和前端类型。 |
| 存档 CAS、快照或导入恢复 | `repositories/saves.py`、`models/save.py` 与 `api/saves.py`。 |
| 数据库连接或表结构 | `db.py`、`repositories/tables.py`、`alembic/`。 |
| 静态配置种类或 catalog | `config_loader.py`、`api/catalog.py`、相应模型和根目录 `tools/validate_config.py`。 |

新增模块先确认完整职责与现有入口，验证范围按实际改动选择；不要仅为增加目录而额外建立透传层。
