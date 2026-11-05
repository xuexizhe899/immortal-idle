# T02 · 存档模型、多档与 CAS

- 里程碑：M1 ｜ 依赖：T01 ｜ 对应文档：DESIGN.md 第 4 节

## 目标
单机多档的存档落地：整档一份 `state_json`，关系列存元数据，写入带乐观锁，支持快照与回滚。

## 已锁定决策
1. SQLite + aiosqlite，单库多档，WAL
2. 整档 `state_json`，弟子是数组内的独立对象，**不按弟子拆行存储**
3. `revision` 做 CAS 乐观锁；`schema_version` 驱动迁移；重大变更前写 `save_snapshots`
4. `owner_id` 默认 1 仅作预留，不做账号体系、不做鉴权
5. 存档只存 `asset_id`，绝不存图片 base64 或生图 URL

## 要做的事
1. Alembic 建 `save_slots`、`save_snapshots`（字段见 DESIGN.md 4.2），确认可升可降
2. Pydantic 定义 `GameState` 及子模型（meta/resources/duty_slots/duty_events/disciples/inventory/unlocks/progress/active_run/rng/logs）
3. Repository：读取、创建、复制、删除、列出槽位、导出/导入 JSON、快照写入与回滚
4. CAS 写入：`UPDATE ... WHERE slot_id=? AND revision=?`，影响 0 行时重读重算，不覆盖
5. 迁移框架：`schema_version` 递增 + 迁移函数注册表，老档读入自动升级
6. `logs[]` 限长策略，避免存档无限膨胀

## 产出物
- `backend/app/models/`、`backend/app/repositories/`、Alembic 迁移、多档与 CAS 测试

## 验收
- [x] 过期 revision 的写入被拒（`test_cas_rejects_stale_revision`），已有数据不被覆盖
- [x] 快照可回滚，回滚后 revision 继续递增而非归零（`test_snapshot_and_rollback`）
- [x] 导出 → 导入往返状态一致（`test_export_import_roundtrip`）
- [x] Alembic upgrade / downgrade 实测可循环；`migrate()` 预留 schema_version 升级入口
- [x] 导出内容不含 base64 图片或生图链接（`test_export_contains_no_image_payload`）

## 不做
结算算法（T04）、值守（T03）、前端界面。

## 何时才允许拆行（现在不做）
单档弟子 > 1000，或 `state_json` > 5MB，或需要按弟子检索/跨档排行。届时只把 `disciples` 挪到独立表并 `schema_version + 1`，其余不动。

## 执行记录（2026-11-05）
- 表：`save_slots` / `save_snapshots`，迁移 `0001_init`；实测 `upgrade → downgrade → upgrade` 可循环
- 模型：`GameState` 及子模型（Resources / DiscipleState / DutySlot / DutyEvent / ActiveRun）；`SaveExport` 作为导入的边界校验
- 仓储：`SaveRepository`，整档 JSON + revision CAS，含复制 / 导出导入 / 快照 / 回滚
- 接口：10 条路由（列表、创建、导入、读取、写入、删除、复制、导出、建快照、回滚）；冒烟实测 200 与 409 符合预期
- 依赖修正：SQLAlchemy async 需要 `sqlalchemy[asyncio]`（greenlet），pyproject 已更新
- 前端契约重新生成后 build 通过；`backend/data/` 已 gitignore
- 测试：`backend/tests/test_saves.py` 7 个用例，全库 9 passed
