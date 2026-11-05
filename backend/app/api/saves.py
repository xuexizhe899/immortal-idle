"""存档接口：多档增删改查、复制、导入导出、快照回滚。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.models.save import GameState, SaveExport, SaveSlotMeta
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves", tags=["saves"])


class CreateSlotRequest(BaseModel):
    """新建存档请求。"""

    name: str


class SaveStateRequest(BaseModel):
    """写入存档请求，revision 用于 CAS。"""

    revision: int
    state: GameState


class DuplicateRequest(BaseModel):
    """复制存档请求。"""

    name: str


class SnapshotRequest(BaseModel):
    """创建快照请求。"""

    reason: str = "manual"


async def get_repo(request: Request) -> AsyncIterator[SaveRepository]:
    """请求级依赖：创建会话并在请求结束后关闭。"""
    async with request.app.state.session_factory() as session:
        yield SaveRepository(session)


@router.get("", response_model=list[SaveSlotMeta])
async def list_slots(repo: SaveRepository = Depends(get_repo)) -> list[SaveSlotMeta]:
    """列出全部存档槽。"""
    return await repo.list_slots()


@router.post("", status_code=201)
async def create_slot(
    payload: CreateSlotRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """新建存档槽，返回 slot_id。"""
    slot_id = await repo.create_slot(payload.name)
    return {"slot_id": slot_id}


@router.post("/import", status_code=201)
async def import_slot(
    payload: SaveExport, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """从导出载荷导入为新槽。"""
    slot_id = await repo.import_slot(payload)
    return {"slot_id": slot_id}


@router.get("/{slot_id}")
async def get_slot(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """读取存档内容与当前 revision。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return {"revision": revision, "state": state.model_dump(mode="json")}


@router.put("/{slot_id}")
async def put_slot(
    slot_id: int,
    payload: SaveStateRequest,
    repo: SaveRepository = Depends(get_repo),
) -> dict:
    """按 revision 写入存档；冲突返回 409。"""
    if not await repo.save_state(slot_id, payload.state, payload.revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重新读取")
    return {"ok": True, "revision": payload.revision + 1}


@router.delete("/{slot_id}")
async def delete_slot(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """删除存档槽及其快照。"""
    if not await repo.delete_slot(slot_id):
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"ok": True}


@router.post("/{slot_id}/duplicate", status_code=201)
async def duplicate_slot(
    slot_id: int,
    payload: DuplicateRequest,
    repo: SaveRepository = Depends(get_repo),
) -> dict:
    """复制存档为新槽。"""
    new_id = await repo.duplicate_slot(slot_id, payload.name)
    if new_id is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"slot_id": new_id}


@router.get("/{slot_id}/export")
async def export_slot(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """导出存档为可移植 JSON。"""
    data = await repo.export_slot(slot_id)
    if data is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return data


@router.post("/{slot_id}/snapshots", status_code=201)
async def create_snapshot(
    slot_id: int,
    payload: SnapshotRequest,
    repo: SaveRepository = Depends(get_repo),
) -> dict:
    """为存档创建快照。"""
    snapshot_id = await repo.snapshot(slot_id, payload.reason)
    if snapshot_id is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"snapshot_id": snapshot_id}


@router.post("/{slot_id}/rollback/{snapshot_id}")
async def rollback(
    slot_id: int, snapshot_id: int, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """回滚到指定快照。"""
    if not await repo.rollback(slot_id, snapshot_id):
        raise HTTPException(status_code=404, detail="存档或快照不存在")
    return {"ok": True}
