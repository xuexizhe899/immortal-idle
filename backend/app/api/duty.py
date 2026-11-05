"""值守编制接口：查看、上岗、下岗。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.saves import get_repo
from app.config_loader import load_disciples
from app.domain.duty import assign, compute_rates, members_of, unassign
from app.models.save import GameState
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/duty", tags=["duty"])


class DutyChangeRequest(BaseModel):
    """上岗 / 下岗请求，revision 用于 CAS。"""

    revision: int
    disciple_id: str


def utcnow() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def duty_payload(state: GameState, revision: int) -> dict:
    """把编制与加成打包成接口返回结构。"""
    return {
        "revision": revision,
        "duty": [slot.model_dump(mode="json") for slot in state.duty_slots],
        "rates": compute_rates(members_of(state, load_disciples())),
    }


async def change_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository, join: bool
) -> dict:
    """上岗 / 下岗的共用流程：读档 → 校验 revision → 变更 → CAS 写回。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    if payload.revision != revision:
        raise HTTPException(status_code=409, detail="revision 冲突，请重新读取")

    change = assign if join else unassign
    error = change(state, payload.disciple_id, load_disciples(), utcnow())
    if error:
        raise HTTPException(status_code=400, detail=error)

    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重新读取")
    return duty_payload(state, revision + 1)


@router.get("")
async def get_duty(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """查看当前值守编制与产出加成。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return duty_payload(state, revision)


@router.post("/assign")
async def assign_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """把弟子加入值守编制。"""
    return await change_duty(slot_id, payload, repo, join=True)


@router.post("/unassign")
async def unassign_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """把弟子移出值守编制。"""
    return await change_duty(slot_id, payload, repo, join=False)
