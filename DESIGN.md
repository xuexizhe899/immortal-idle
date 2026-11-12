# 修仙放置 x 休闲肉鸽 · 实施文档

> v0.1 · 2026-11-05 · 来源：grill-me 六支设计拷问收口
> 状态：23 项决策已确认，无悬空答案，可据此开工

---

## 0. 一页速览

| 项 | 结论 |
|---|---|
| 形态 | Web-first，浏览器即运行时；自用、不盈利、单人单机多档 |
| 前端 | Vue 3 + TypeScript + Vite + Pinia；当前演出为 Vue / SVG / CSS，PixiJS 仅作可选演出依赖 |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 async + Pydantic v2（项目内独立 venv） |
| 存储 | SQLite + aiosqlite，单库多档，WAL；存档整档一份 `state_json` |
| 契约 | Pydantic → OpenAPI → 生成 TS 类型，前后端单一来源 |
| 配置 | `config/*.json` 按实体拆文件进 Git，CI 校验悬空引用 |
| 美术 | 云端生图 API，开发期批量生成，运行时不调 API；本机零安装 |
| 部署 | Docker Compose（app + Caddy），CI 构建镜像、服务器只拉取 |
| 服务器 | 4h4g Linux 常驻；本机 Win11 / 16G / 3060 12G / 400G 只负责开发 |
| 首版范围 | 只铺爬塔内容（20 层，第 20 层为首领），远征/入侵留配置位 |
| 完成判定 | 第 11 节 9 条验收全过 |

---

## 1. 约束与目标

**目标**：练「前端游戏架构 + 后端工程化 + 部署运维」，同时做出一个能长期打发时间的游戏。

**质量拉满**（做）：分层、迁移脚本、幂等写入、结构化日志、测试、备份、可观测、可一键重建。

**规模不碰**（不做）：多用户与注册登录、RBAC、支付订单、活动运营后台、Redis/消息队列/限流熔断、反作弊、灰度与集群、Prometheus 监控体系。

**设备约束**：本机不装游戏引擎、不装本地生图环境、不碰现有 Python venv（尤其不往 `~/.workbuddy/binaries/python/envs/default` 装包）。3060 / 16G / 400G 全部留给开发与浏览器。

---

## 2. 技术选型（已锁定）

| 层 | 选型 | 理由 |
|---|---|---|
| 渲染 | Vue 3 + Vite（UI），当前用 SVG / CSS 演出 | 面板与列表使用 DOM，战报驱动演出；保留 PixiJS 依赖供确有需要的复杂演出使用，不引入第二套玩法状态 |
| 语言 | TS 前端 / Python 后端 | 后端是熟练栈，才能把"质量拉满"真正做满；换语言只练到工具链 |
| ORM | SQLAlchemy 2.0 async + Alembic | 迁移可升可降；SQLite 需 `batch_alter_table` |
| 数据库 | SQLite + WAL | 单用户 QPS≈1；零常驻内存；备份即单文件；PostgreSQL 属于"规模" |
| 存档 | 整档 `state_json` + 关系列元数据 | 一次 UPDATE 即原子存档；按弟子拆行会破坏快照/回滚/CAS，属提前优化 |
| 契约 | OpenAPI → TS 类型 | 配置、存档、DTO 单一来源，消除前后端口径不一致 |
| 部署 | Docker Compose + Caddy + CI | 镜像可回滚；Caddy 自动 HTTPS；本机无需 Docker |
| 生图 | 云端 API（见第 8 节） | 新模型已解决角色一致性；本机不必装 SD/ComfyUI |

---

## 3. 仓库结构

分层职责、允许依赖、新增文件归属与资产引用统一见 [ARCHITECTURE.md](ARCHITECTURE.md)。以下仅列当前主要位置；规范中的目标目录按真实迁移逐步建立。

人物、场景与主城的公共画风、身份一致性、提示词要求和图像验收见 [ART_DIRECTION.md](ART_DIRECTION.md)。

```
immortal-idle/
  ARCHITECTURE.md             # 分层、依赖、目录与资产规范
  DESIGN.md
  config/                    # 静态定义；本局所需定义在出发时固化进存档快照
    disciples/               # 弟子模板
    skills/                  # 主动、被动技能
    bonds/                   # 羁绊与技能修正
    affixes/                 # 词条
    recipes/                 # 丹方、器方
    materials/ enemies/ events/ modes/
    ui/                      # 主城背景与建筑热区
    style/                   # 风格约定
  backend/
    app/
      main.py                # 启动与应用组装
      api/                   # HTTP、当前应用编排与响应组装
      domain/                # 战斗、出征、结算、成长等规则
      models/                # Pydantic 存档、战斗模型与契约
      repositories/          # SQLite 整档访问、CAS、快照
      db.py                  # 引擎、WAL 与会话工厂
      config_loader.py       # 静态配置加载与缓存
    alembic/
    tests/
  frontend/
    src/
      views/                 # 页面与功能面板
      components/            # 通用 UI（ui/）与业务组件（game/）
      rendering/             # 战报播放、敌人与技能特效、昼夜视觉
      presentation/          # 游戏文案映射与资源路径解析
      shared/                # 纯数值格式化等基础函数
      stores/                # Pinia 响应镜像、命令与偏好
      api/                   # HTTP 客户端与类型别名
      generated/             # 生成的 TS 类型，忽略且不手改
    public/assets/           # 正式运行图片及 SVG 图标
    tests/
  assets/                    # master、提示、脱敏生成记录与原始输出
  tools/                     # 生成、处理、校验、测量及测试
  artifacts/                 # 草稿、截图、报告与验收证据
  docs/                      # 方案与审查
  tasks/                     # 任务卡
  .github/workflows/ci.yml
```

Docker Compose、Caddy 与备份恢复仍为部署规划；当前没有 `deploy/` 和备份恢复脚本，现有 CI 执行检查与契约生成，尚无镜像构建任务。

---

## 4. 数据模型

### 4.1 静态配置示例

`config/disciples/zhugeliang.json`

```json
{
  "id": "zhugeliang",
  "name": "诸葛亮",
  "title": "卧龙",
  "origin": "sanguo",
  "rarity": 3,
  "lean": "support",
  "asset_id": "zhugeliang",
  "base_stats": { "hp": 96, "atk": 12, "def": 9, "spd": 10 },
  "skill": "bagua",
  "passive": "mou-ding",
  "bonds": []
}
```

`skill` / `passive` 是技能表 id 引用，定义集中在 `config/skills/`，避免内联重复。

**引用完整性规则**：`skill` / `passive` 必须存在于 `config/skills/` 且类型匹配、`bonds[*]` 必须存在于 `config/bonds/`、`asset_id` 必须对应 `frontend/public/assets/<asset_id>.png`、`lean` 必须是四倾向之一。任一悬空 → CI 失败。

### 4.2 数据库表

```
save_slots
  slot_id        INTEGER PRIMARY KEY
  owner_id       INTEGER NOT NULL DEFAULT 1   -- 为将来开放预留，不做账号体系
  name           TEXT
  created_at     TEXT NOT NULL
  updated_at     TEXT NOT NULL
  last_settled_at TEXT NOT NULL               -- 产出锚点，UTC
  schema_version INTEGER NOT NULL
  revision       INTEGER NOT NULL             -- CAS 乐观锁
  state_json     TEXT NOT NULL

save_snapshots
  id INTEGER PRIMARY KEY
  slot_id INTEGER NOT NULL
  schema_version INTEGER NOT NULL
  state_json TEXT NOT NULL
  reason TEXT          -- migration / manual / before_run
  created_at TEXT NOT NULL
```

### 4.3 `state_json` 结构

```
meta            { schema_version, created_at }
resources       { cultivation, spirit_stone, stamina }
duty_slots[]    { disciple_id, assigned_at }          # 值守编制，上限 6
duty_events[]   { at, snapshot }                      # 值守变更事件流，分段补算用
disciples[]     { id, template_id, level, exp, realm,
                  stats, skills, equipment[6], buffs,
                  injury_stacks, injured_until,
                  busy_until }
inventory       { materials{}, pills{}, artifacts{} }
unlocks         { recipes[], disciples[], bonds[] }
progress        { tower_floor, expedition, invasion_waves }
active_run      null | { run_seed, rng_cursor, mode, party[],
                         node_index, nodes[], affixes[],
                         pending_loot[], started_at }
rng             { global_seed, cursor }
logs[]          # 结算与事件日志，需限长，避免无限膨胀
```

**硬规则**：存档只存 `asset_id`，绝不存图片 base64 或生图 URL。

### 4.4 CAS 写入

```sql
UPDATE save_slots
SET state_json = ?, revision = revision + 1, last_settled_at = ?, updated_at = ?
WHERE slot_id = ? AND revision = ?
```

影响行数为 0 → 重读最新档并重算，不覆盖他人写入。

---

## 5. 时间推进与惰性结算（核心算法）

### 5.1 规则

- 随时间推进的只有：修为/灵石、行动力恢复、伤势消退、由值守派生的资源。
- `active_run` **不推进**：关浏览器停在"等待选节点/选词条"，回来接着打。
- 全档推进、切档不冻结（`frozen` 方案已作废，不得残留）。
- 12 小时软封顶：超出部分直接丢弃；不设仓库硬上限。
- 行动力不设独立上限，只受 12h 封顶约束。
- 服务端 UTC 单调时钟；`now - last_settled_at` 为负时 clamp 为 0 并记录告警。
- 无常驻 tick，一切在读取/切档/出征时惰性补算。

### 5.2 补算伪代码

```python
def settle(slot, now):
    elapsed = clamp(now - slot.last_settled_at, 0, IDLE_CAP)   # 12h
    if elapsed <= 0:
        return slot

    # 1) 值守速率随时间变化：按事件流分段求和，不做一次乘法
    for seg in split_by_duty_events(slot.duty_events, slot.last_settled_at, now):
        rates = compute_rates(seg.snapshot, slot.disciples)     # 四倾向映射
        apply_production(slot, rates, seg.duration, budget=elapsed)

    # 2) 行动力与伤势用真实时间戳
    slot.resources.stamina += elapsed / STAMINA_INTERVAL        # 1 点 / 2h 起调
    slot.disciples = [drop_expired_injuries(d, now) for d in slot.disciples]

    slot.last_settled_at = now
    return slot
```

### 5.3 测试要点

- 同一档、同一 `now` 重复补算结果一致（幂等）
- 分两次补算与一次补算结果一致（可分段）
- 值守中途换人的分段结果与手工核算一致
- `now` 回拨不产生负产出，并产生告警日志
- 超过 12h 的部分被丢弃

---

## 6. 随机性

- 出征开始时服务端生成 `run_seed`，整局共用；存档只存 `run_seed` + `rng_cursor`。
- 使用确定性 PRNG（PCG32 / xorshift128），禁用 `Math.random()` 与全局 `random`。
- **消费顺序固定**：地图节点 → 事件 → 词条三选一 → 敌人编成 → 战斗随机（暴击/闪避）。
- 数值公式（伤害、成长、掉落数量）保持纯确定性，不掺随机，保证 property-based 测试可覆盖。
- 随机全在服务端，前端只渲染，因此无需 JS/Python 双端 PRNG 对齐。
- 同一 `run_seed` + 相同决策序列 → 结果完全一致，可重放、可复盘。

**加权三选一**：每选定一个词条，其所属协同组后续权重 +50%（可叠加），其余组不变；单次三选一不重复；组权重表放 `config/affixes/`。

---

## 7. 玩法规格

### 7.1 双层边界

- **局外永久层**：弟子 roster、境界、资源、值守、丹方/器方解锁、图鉴、挂机产出。永不重置。
- **局内出征层**：`active_run`（队伍快照、节点、词条、局内血量、待结算战利品）。结束即清空。
- 耦合仅两处：出征带走队伍 + 补给 + 行动力；结算带回战利品。

### 7.2 出征状态机

```
idle -> preparing(选队/补给/扣行动力/生成 seed)
     -> node_choices(选节点)
     -> affix_choice(加权三选一)
     -> battle(自动)
     -> node_choices ... -> cleared | defeated
     -> settle(按到达层数发部分收益 -> 写回永久层 -> 清空 active_run -> 解除 busy)
```

中途关闭浏览器不视为失败，`active_run` 原样保留。

出发时固化队伍战斗快照：基础属性、等级/境界、伤势折扣、永久加成与羁绊不随现实时间变化；只有本局新选词条影响后续战力。旧出征首次恢复时在自然消伤之前补建兼容快照，不消费随机数。

### 7.3 失败成本

| 项 | 规则 |
|---|---|
| 行动力 | 出发即扣，胜败不退 |
| 补给 | 出发即扣，胜败不退 |
| 伤势 | 最多 3 层，每层 -10% 攻，仅出征战斗生效 |
| 消退 | `injured_until` 到期自动清（每层约 4h，可调），疗伤丹立即清 |
| 收益 | 按到达层数给部分收益，层数越深越多 |
| 不碰 | 不删弟子、不掉境界、不删装备、不罚挂机产出 |
| 保底 | 带伤弟子可值守，也可带减攻出征低层拿基础收益；值守与出征互斥 |

### 7.4 节奏

- 单局 3–5 分钟 / 8–12 节点；每天上线 20–30 分钟（可拆 1–2 次）。
- 每局 1 点行动力；恢复约 1 点 / 2 小时起调，12h 封顶提供 ≥6 点。
- 三种模式共享行动力，玩家自行分配。

### 7.5 值守编制

- 上限 6 人，与出征队伍互斥；带伤弟子可值守。
- 四倾向映射：攻 → 修为；防 → 灵石；辅 → 行动力恢复与伤势消退；炼 → 材料/丹药产出。
- 品质档定系数、境界定基础值，走加区 +%，不做乘区。
- 每次变更写入 `duty_events`，补算按事件分段。

### 7.6 三种模式（同一引擎，仅配置表不同）

| 模式 | 定位 | 产出 | 首版 |
|---|---|---|---|
| 爬塔 | 主线成长，冲层 | 修为、解锁点、声望/材料来源之一 | 共 20 层，末层首领 |
| 远征 | 固定 8–12 节点 | 材料、丹方、器方 | 仅占位 |
| 入侵者 | 防守，挂机积攒波次有上限，上线自选迎击 | 声望、稀有材料 | 仅占位 |

不迎击只损失少量资源，不掉弟子、不产生伤势；**不做真实时间限时事件**。

### 7.7 内容量级

- 弟子 12–20 个（三国/神话/历史各 4–6）；3 档品质 × 4 倾向 × 1 专属技能 × 1 被动 × 羁绊组
- 招聘：声望/材料定向解锁 + 少量"云游访贤"随机事件；重复弟子转羁绊经验或通用碎片，不做付费抽卡
- 词条 40–60 条 / 6–8 协同组（首版 20 条 / 3 组）
- 丹方、器方各 12–20，材料 20–30，单步合成为主（首版各 6 条）
- 爬塔 100 层分 5 段；敌人 20–30 种，事件 20–30 条
- 羁绊首版 3–4 组

### 7.8 当前原型的可玩规则（2026-11-11）

- 新档获得 500 声望、3 行动力及六类入门材料，用于从零体验招募与炼制；旧档和导入档不补发。
- 定向招募；已拥有的角色按半价提升境界。修炼升级消耗当前等级 × 20 修为、× 10 灵石。
- 等级每级增加 10% 战力成长，境界每阶增加 5%；速度百分比以 0.2 权重计入当前总战力公式。当前战斗按队伍总战力确定胜负，独立招式暂为人物资料预览。
- 炼制立即生效；出征期间不通过炼制改变本局阵容。挂机与爬塔提供六类材料，挂机材料的小数余量跨次保存。
- 玩家发起的决策与消耗指令携带 `revision`，冲突后刷新状态；网络结果不确定时只查询最新状态，不自动重放扣费操作。首次载入的离线补算可省略版本。

### 7.9 主城入口与环境（2026-11-11）

主城只有七个功能建筑，图片与百分比热区一一对应；不再在完整城图上叠加旧建筑。入口始终有文字，主城与底部固定功能栏组成一屏；底栏提供宗门、弟子、值守、炼丹、炼器、问道六入口，与建筑共用面板调度。未开放码头仅保留地图入口。手机只在地图区域横向浏览，不推动整个页面。

首页不展示独立阵容卡片和大段回报。当前目标用可点击浮签指向下一步，场景右下收取收益，详细挂机与最近出征回报进入宗门总览。问道按真实状态显示“问道／继续出征／待结算”，阵容仍在弟子及出征准备中管理。底栏使用本地像素 SVG；气泡提示避让底栏，弹窗层级高于场景与导航。

| 建筑 | 入口与面板用途 |
|---|---|
| 宗门主殿 | 总览、离线收益、当前成长目标；存档管理置于内部次级页签 |
| 藏经阁 | 人物、招贤、详情与出征阵容；底栏“弟子”直达 |
| 演武场 | 值守编制；人数与主要每小时产出在面板及入口说明中显示 |
| 问道塔 | 最高层、出征准备；已有出征显示“继续出征”或“待结算” |
| 炼丹房 | 疗伤与丹药炼制；带伤人数和可炼配方在入口说明中显示 |
| 炼器炉 | 法器炼制；器方、可炼数量与永久加成在入口说明及面板中查看 |
| 远行码头 | 明示尚未开放 |

天色随设备本地时间经历晨、昼、暮、夜，云雾、星月和灯火仅影响视觉；玩家可预览四种天色再切回随时间。收益和行动力仍只按服务端时间结算。所有 16 名现有角色共用细像素、青绿/暖木配色、左上暖光与透明底立绘规范。

---

### 7.10 六人出征与技能羁绊（已实现，2026-11-12）

用户已确认推进技能模块，出征 1–6 人，技能应与羁绊关联并支持多种组合。7.8 的总战力与技能预览描述作为原型历史记录，本期由 T16 自动战斗替代。

当前采用服务端自动回合：技能通过伤害、治疗、护盾和属性增减独立配合，具名羁绊再强化成员技能。支持三人羁绊＋双人羁绊＋自由位、三组双人羁绊，以及少量羁绊搭配功能角色；不按羁绊数量直接判胜负。现有诗圣是值守羁绊，不混入战斗收益。

新局允许 1–6 人，使用逐人气血并跨层保留；合计气血条只做展示。最多 20 轮，回合耗尽显式失败，保留实际剩余气血。现有 16 人的 32 项技能与四组战斗羁绊已接入。项目尚未上线，按用户决定不保留旧出征结构兼容；出发时固化角色、技能、羁绊与相关配置，保留整档存档、CAS 和确定性重放，不自动清理本地数据。

详细触发规则与组合示例见 [T16 · 六人出征、技能与羁绊组合](tasks/T16-skills-and-bonds.md)。Vue、SVG 与 CSS 承担敌人、技能特效和状态标识，复用人物与塔内场景，本期未新增位图。战报支持关键招式/完整演出、跳过、重播及完整明细；交付与检查结果见 [修改汇总](CHANGELOG-2026-11-12.md)。

---

## 8. 美术资产管线

本节记录早期计划与试稿历史，不再作为当前新增图像的完整风格验收规范；以 [ART_DIRECTION.md](ART_DIRECTION.md) 为准。当前生图脚本尚未接入 master 图像参考编辑，历史任务卡的完成勾选不代表身份回喂能力已实现。

### 8.1 资产清单

| 资产 | 数量 | 来源 | 规格 |
|---|---|---|---|
| 全身立绘 | 12–20 | 云端生成 | 最大边 1024 起，2:3，透明底 PNG，统一光照 |
| 头像 | 12–20 | 立绘裁切 | 不单独生成 |
| 战斗小人 | 全体 | 统一模板 + 角色特征层 / 缩小立绘 | 不逐角色生成 |
| 场景图 | 6–10 | 云端生成 | 爬塔 5 段 + 远征 + 入侵，同 style bible |
| UI 图标 | — | SVG 手写 / 图标库 | 不生图 |
| **三视图** | 0 | 不做 | 2D 网页游戏用不到 |

### 8.2 端点与模型

- 主力：`https://frapi.centos.hk/v1/images/generations`（图生图 `/v1/images/edits`），模型 `gpt-image-2.6-sunburst`
- 备选：`https://image.mlgb7.com/v1/images/generations`，模型 `gpt-image-2.5`，支持 `async` + `n`
- **模型名存疑**：示例 curl 写的是 `gpt-image-2`，与指定名不一致，试稿第一步分别打最小请求验证，可用名写回 manifest

### 8.3 管线规则

1. 先定 **style bible**（固定 style prompt + 1–2 张风格参考图），所有请求必带
2. 每个角色先出 1 张正面 master 立绘 → 人工批准 → 派生图经 `/v1/images/edits` 回喂 master 锁身份
3. 生成成功后**立即下载落盘**，绝不把 URL 写进配置、存档或 Git
4. 脚本自带本地去重（prompt + 参数 + style 版本 hash），不依赖服务端幂等
5. 尺寸先按 1K 请求，支持更大再调
6. 每次调用的模型名、prompt、参数、返回文件名写入 `assets/manifest.json` 并进 Git
7. 产物按 `asset_id` 命名放入 `frontend/public/assets/`，与配置对齐
8. API key 只放本地 `.env`，不进仓库；设总调用上限（如 300 次）
9. 成本估算：成品 30–40 张，含返工约 100–150 次调用

### 8.4 试稿阶段必须实测（不可从旧端点继承）

- 可用模型名、尺寸上限、图片 URL 有效期、计费与失败是否扣费、`edits` 参数格式（multipart 或 JSON URL）
- 先用 **3 张立绘 + 1 张场景**验证风格与一致性，再批量

---

## 9. 部署与运维

### 9.1 结构

```
用户浏览器
   └─ HTTPS → Caddy（自动签发证书）
                ├─ /        → frontend dist 静态托管
                └─ /api/*   → app:8000 (FastAPI)
app 容器 ── volume: ./data → SQLite (WAL)
```

- CI（GitHub Actions）：`pytest` + `validate_config.py` + 前端构建 + 镜像构建 → 推 registry
- 服务器只执行 `docker compose pull && docker compose up -d`，不装构建环境
- 本机不装 Docker Desktop
- 回滚 = compose 切回旧 image tag

### 9.2 备份与恢复

- 定时任务：`sqlite3 .backup`（或 `VACUUM INTO`）→ 打包 → 留存 30 天；**禁止裸 `cp` 正在写入的库文件**
- `tools/restore.sh`：停服 → 还原 db → 起服 → 校验
- **必须真实演练一次恢复**，写了脚本不算完成

### 9.3 可观测

结构化日志 + 请求追踪 ID + 全局异常处理；结算异常可定位到 slot 与时间段；时钟回拨、CAS 冲突、补算被 clamp 均记录告警。不上 Prometheus/Grafana。

---

## 10. 开发里程碑

| 里程碑 | 产出 | 判定 |
|---|---|---|
| M0 骨架 | monorepo、venv、Vite、`validate_config.py`、OpenAPI→TS 生成、CI 绿 | 空页面可跑，改坏一个引用 CI 即失败 |
| M1 存档与结算 | 多档、CAS、惰性分段结算、快照、数值测试 | 关浏览器 1 小时后收菜数值正确，可复算 |
| M2 出征链路 | 状态机、种子随机、加权三选一、伤势、结算 | 能完整打完一局并带回战利品，同 seed 可重放 |
| M3 内容与美术 | 弟子/词条/丹方配置、生图脚本、3 张试稿 → 批量 | 12–20 立绘 + 场景图落盘，风格统一 |
| M4 上线 | Compose、Caddy、CI、备份脚本、恢复演练 | 空服务器可一键重建并恢复存档 |
| M5 验收 | 第 11 节 9 条全过 | 首版完成 |

---

## 11. 验收清单

- [ ] 数据不丢：改本地时间不刷收益；时钟回拨 clamp + 告警；强杀进程重启不丢档
- [ ] 能回滚：Alembic 可升可降、`schema_version` 可迁移、镜像可切回旧 tag
- [ ] 可重放：同 `run_seed` 结果一致；值守事件流分段补算可复算
- [ ] 可观测：结构化日志 + 请求追踪 + 全局异常，可定位到 slot 与时间段
- [ ] 可重建：空服务器凭仓库 + 一份备份还原到可玩状态，且已演练
- [ ] 测试：pytest 覆盖数值公式（含 property-based）、离线收益、种子、并发 CAS；CI 提交即跑
- [ ] 配置完整性：CI 校验所有引用 ID 无悬空
- [ ] 备份：定时 `.backup` → 打包 → 留存，且恢复成功过一次
- [ ] 可玩闭环：从零跑通 招弟子 → 值守 → 爬塔 → 受伤 → 炼丹 → 再出征

---

## 12. 开工前待办与风险

1. **两枚 API 密钥曾在对话中明文出现 → 立即作废轮换**，新 key 单独提供、不进仓库
2. 试稿实测新端点参数（见 8.4），旧端点的 1K / 1800s / `X-Request-Id` 规格不可继承
3. 服务器一次性安装 Docker；本机不装
4. 中转服务模型版本可能变：靠 manifest + master 图 + style bible 保证后期追加角色可复现风格
5. 内容量是最大烂尾风险：首版严格只做爬塔内容，其余模式只留配置位

---

## 13. 附录：关键分叉与被推翻的方案（避免重复争论）

| 分叉 | 最终决定 | 被否方案与原因 |
|---|---|---|
| 桌面 or Web | Web-first 硬约束 | 客户端转 Web 近乎重写；无多端分发需求 |
| 要不要游戏引擎 | 不装，Vue + PixiJS | 引擎带来第二套状态源、UI 重造、产物变重、资产管线多一道 |
| 后端语言 | Python / FastAPI | TS 全栈的共享类型优势可由 OpenAPI 生成替代；换语言反而拉低质量 |
| 数据库 | SQLite | PostgreSQL/MySQL 属"规模"，且占 4G 服务器常驻内存 |
| 存档拆行 | 整档一份 JSON | 按弟子拆行破坏原子存档、CAS、快照回滚，属提前优化；触发线：弟子 >1000 或 state_json >5MB |
| 一局定义 | 一次出征，非整个存档 | 轮回重修会清零永久层，与放置冲突；纯随机事件则丢失肉鸽 build |
| 失败惩罚 | 行动力 + 补给 + 可消退伤势 + 部分收益 | 零成本会让三选一失去张力；纯丹药解伤会死锁 |
| 切档冻结 | 全档推进，不冻结 | 曾选 B（冻结），后因仅 2–3 个档回滚；`frozen` 方案与字段级区分全部作废 |
| 三视图 | 不做 | 三视图面向 3D 建模/骨骼绑定/AI 视频；2D 网页游戏只用正面立绘 |
| 生图环境 | 云端 API，本机零安装 | 本地 ComfyUI/LoRA 已被新模型的一致性能力取代 |
| 首版内容 | 只铺爬塔 | 三模式内容成本是三倍，代码成本近乎为零 |
