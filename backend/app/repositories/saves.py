"""存档仓储：多档 CRUD、CAS 写入、快照与回滚。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.save import CURRENT_SCHEMA_VERSION, GameState, SaveExport, SaveSlotMeta
from app.repositories.tables import save_slots, save_snapshots


def utcnow() -> datetime:
    """当前 UTC 时间，存档内所有时间戳统一用它。"""
    return datetime.now(timezone.utc)


def migrate(state: GameState) -> GameState:
    """把旧版存档升级到当前 schema_version；未来版本在此追加迁移分支。"""
    if state.schema_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"存档版本 {state.schema_version} 高于程序支持的 {CURRENT_SCHEMA_VERSION}"
        )
    state.schema_version = CURRENT_SCHEMA_VERSION
    return state


class SaveRepository:
    """单机多档存档的读写入口，所有写入都是整档 + revision CAS。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_slots(self) -> list[SaveSlotMeta]:
        """列出全部存档槽，按更新时间倒序。"""
        rows = await self.session.execute(
            select(save_slots).order_by(save_slots.c.updated_at.desc())
        )
        return [self._meta(row) for row in rows.mappings()]

    async def create_slot(self, name: str, state: GameState | None = None) -> int:
        """新建存档槽并返回 slot_id。"""
        now = utcnow().isoformat()
        state = state or GameState()
        result = await self.session.execute(
            insert(save_slots).values(
                owner_id=1,
                name=name,
                created_at=now,
                updated_at=now,
                last_settled_at=now,
                schema_version=state.schema_version,
                revision=1,
                state_json=state.model_dump_json(),
            )
        )
        await self.session.commit()
        return int(result.inserted_primary_key[0])

    async def get_state(self, slot_id: int) -> tuple[GameState, int] | None:
        """读取存档与当前 revision；槽不存在返回 None。"""
        row = await self.session.execute(
            select(save_slots.c.state_json, save_slots.c.revision).where(
                save_slots.c.slot_id == slot_id
            )
        )
        record = row.first()
        if record is None:
            return None
        state = migrate(GameState.model_validate_json(record.state_json))
        return state, int(record.revision)

    async def save_state(
        self, slot_id: int, state: GameState, expected_revision: int
    ) -> bool:
        """CAS 写入：revision 不匹配则不覆盖，返回是否写入成功。"""
        now = utcnow().isoformat()
        result = await self.session.execute(
            update(save_slots)
            .where(
                save_slots.c.slot_id == slot_id,
                save_slots.c.revision == expected_revision,
            )
            .values(
                state_json=state.model_dump_json(),
                schema_version=state.schema_version,
                revision=save_slots.c.revision + 1,
                updated_at=now,
                last_settled_at=now,
            )
        )
        await self.session.commit()
        return result.rowcount == 1

    async def delete_slot(self, slot_id: int) -> bool:
        """删除存档槽及其全部快照，返回是否删掉了记录。"""
        await self.session.execute(
            delete(save_snapshots).where(save_snapshots.c.slot_id == slot_id)
        )
        result = await self.session.execute(
            delete(save_slots).where(save_slots.c.slot_id == slot_id)
        )
        await self.session.commit()
        return result.rowcount == 1

    async def duplicate_slot(self, slot_id: int, new_name: str) -> int | None:
        """复制一份存档为新槽；源槽不存在返回 None。"""
        loaded = await self.get_state(slot_id)
        if loaded is None:
            return None
        state, _ = loaded
        return await self.create_slot(new_name, state)

    async def export_slot(self, slot_id: int) -> dict | None:
        """导出存档为可移植字典；槽不存在返回 None。"""
        row = await self.session.execute(
            select(save_slots).where(save_slots.c.slot_id == slot_id)
        )
        record = row.mappings().first()
        if record is None:
            return None
        state = GameState.model_validate_json(record["state_json"])
        return SaveExport(name=record["name"], state=state).model_dump(mode="json")

    async def import_slot(self, payload: SaveExport) -> int:
        """从导出载荷导入为新槽，返回 slot_id。"""
        return await self.create_slot(payload.name, migrate(payload.state))

    async def snapshot(self, slot_id: int, reason: str) -> int | None:
        """为当前存档写一份快照；槽不存在返回 None。"""
        loaded = await self.get_state(slot_id)
        if loaded is None:
            return None
        state, _ = loaded
        result = await self.session.execute(
            insert(save_snapshots).values(
                slot_id=slot_id,
                schema_version=state.schema_version,
                state_json=state.model_dump_json(),
                reason=reason,
                created_at=utcnow().isoformat(),
            )
        )
        await self.session.commit()
        return int(result.inserted_primary_key[0])

    async def rollback(self, slot_id: int, snapshot_id: int) -> bool:
        """把指定快照写回存档；revision 继续递增，不重置 CAS 计数。"""
        loaded = await self.get_state(slot_id)
        if loaded is None:
            return False
        _, revision = loaded
        row = await self.session.execute(
            select(save_snapshots.c.state_json).where(
                save_snapshots.c.id == snapshot_id,
                save_snapshots.c.slot_id == slot_id,
            )
        )
        record = row.first()
        if record is None:
            return False
        state = migrate(GameState.model_validate_json(record.state_json))
        return await self.save_state(slot_id, state, revision)

    @staticmethod
    def _meta(row) -> SaveSlotMeta:
        """把查询行转换为元信息模型（时间戳由 Pydantic 解析）。"""
        return SaveSlotMeta(
            slot_id=row["slot_id"],
            name=row["name"],
            revision=row["revision"],
            schema_version=row["schema_version"],
            last_settled_at=row["last_settled_at"],
            updated_at=row["updated_at"],
        )
