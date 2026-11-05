"""结算接口：打开存档时调用一次，补算离线挂机产出。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.domain.settle import settle
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves", tags=["settle"])


def utcnow() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


@router.post("/{slot_id}/settle")
async def settle_slot(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """对存档做一次惰性结算并写回，返回本次收益与最新状态。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded

    last_settled_at = await repo.get_last_settled_at(slot_id)
    if last_settled_at is None:
        raise HTTPException(status_code=404, detail="存档不存在")

    report = settle(state, last_settled_at, utcnow())
    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重试")

    return {
        "revision": revision + 1,
        "elapsed_hours": round(report.elapsed_hours, 4),
        "dropped_hours": round(report.dropped_hours, 4),
        "gained": {
            "cultivation": round(report.cultivation, 2),
            "spirit_stone": round(report.spirit_stone, 2),
            "stamina": round(report.stamina, 2),
        },
        "warnings": report.warnings,
        "state": state.model_dump(mode="json"),
    }
