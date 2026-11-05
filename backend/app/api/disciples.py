"""弟子接口：疗伤。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.domain.injuries import heal
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/disciples", tags=["disciples"])

HEALING_PILL = "healing_pill"


@router.post("/{disciple_id}/heal")
async def heal_disciple(
    slot_id: int, disciple_id: str, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """消耗一颗疗伤丹，立即清除该弟子的全部伤势。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded

    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        raise HTTPException(status_code=404, detail="弟子不存在")
    if state.inventory.get(HEALING_PILL, 0) < 1:
        raise HTTPException(status_code=400, detail="疗伤丹不足")

    state.inventory[HEALING_PILL] -= 1
    if state.inventory[HEALING_PILL] <= 0:
        del state.inventory[HEALING_PILL]
    heal(disciple)

    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重试")

    return {
        "revision": revision + 1,
        "injury_stacks": disciple.injury_stacks,
        "healing_pill": state.inventory.get(HEALING_PILL, 0),
    }
