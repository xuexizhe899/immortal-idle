"""存档仓储测试：多档、CAS、快照回滚、导入导出。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import create_engine
from app.models.save import SaveExport
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata


@pytest_asyncio.fixture()
async def session_factory(tmp_path: Path) -> async_sessionmaker[AsyncSession]:
    """临时 SQLite 文件库，建表后返回会话工厂，用完释放引擎。"""
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_create_and_get(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """新建存档 revision 为 1，状态是空 GameState。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("档一")
        loaded = await repo.get_state(slot_id)

    assert loaded is not None
    state, revision = loaded
    assert revision == 1
    assert state.resources.spirit_stone == 0


async def test_cas_rejects_stale_revision(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """过期 revision 的写入被拒绝，已有数据不被覆盖。"""
    async with session_factory() as session:
        slot_id = await SaveRepository(session).create_slot("档一")

    async with session_factory() as session_a, session_factory() as session_b:
        repo_a = SaveRepository(session_a)
        repo_b = SaveRepository(session_b)
        state_a, rev_a = await repo_a.get_state(slot_id)
        state_b, rev_b = await repo_b.get_state(slot_id)

        state_a.resources.cultivation = 100
        assert await repo_a.save_state(slot_id, state_a, rev_a) is True

        state_b.resources.cultivation = 999
        assert await repo_b.save_state(slot_id, state_b, rev_b) is False

    async with session_factory() as session:
        state, revision = await SaveRepository(session).get_state(slot_id)

    assert state.resources.cultivation == 100
    assert revision == 2


async def test_snapshot_and_rollback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """回滚把快照内容写回，revision 继续递增而不是归零。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("档一")
        snapshot_id = await repo.snapshot(slot_id, "before")

        state, revision = await repo.get_state(slot_id)
        state.resources.spirit_stone = 50
        assert await repo.save_state(slot_id, state, revision) is True

        assert await repo.rollback(slot_id, snapshot_id) is True
        rolled, rolled_revision = await repo.get_state(slot_id)

    assert rolled.resources.spirit_stone == 0
    assert rolled_revision == 3


async def test_export_import_roundtrip(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """导出再导入得到一份内容相同的新槽。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("原档")

        state, revision = await repo.get_state(slot_id)
        state.resources.spirit_stone = 77
        state.tower_floor = 3
        assert await repo.save_state(slot_id, state, revision) is True

        payload = await repo.export_slot(slot_id)
        new_id = await repo.import_slot(SaveExport.model_validate(payload))
        copied, _ = await repo.get_state(new_id)

    assert new_id != slot_id
    assert copied.resources.spirit_stone == 77
    assert copied.tower_floor == 3


async def test_duplicate_slot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """复制出的槽是独立副本，改动互不影响。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("原档")
        new_id = await repo.duplicate_slot(slot_id, "副本")

        state, revision = await repo.get_state(new_id)
        state.resources.cultivation = 1
        assert await repo.save_state(new_id, state, revision) is True

        original, _ = await repo.get_state(slot_id)

    assert new_id != slot_id
    assert original.resources.cultivation == 0


async def test_list_and_delete(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """列表包含新建槽，删除后读不到。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("档一")
        await repo.create_slot("档二")
        slots = await repo.list_slots()

        assert await repo.delete_slot(slot_id) is True
        assert await repo.get_state(slot_id) is None

    assert {slot.name for slot in slots} == {"档一", "档二"}


async def test_export_contains_no_image_payload(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """导出内容不包含 base64 图片或生图链接。"""
    async with session_factory() as session:
        repo = SaveRepository(session)
        slot_id = await repo.create_slot("档一")
        payload = await repo.export_slot(slot_id)

    text = json.dumps(payload, ensure_ascii=False)
    assert "data:image" not in text
    assert "http://" not in text
    assert "https://" not in text
