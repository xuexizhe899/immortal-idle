"""招募接口：按模板招募弟子，已拥有则升境界。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.saves import get_repo
from app.config_loader import load_disciples
from app.domain.recruit import recruit
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/recruit", tags=["recruit"])


class RecruitRequest(BaseModel):
    """招募请求：弟子模板 id。"""

    template_id: str


@router.post("")
async def recruit_disciple(
    slot_id: int, payload: RecruitRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """按模板招募弟子；已拥有时提升境界。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded

    error = recruit(state, payload.template_id, load_disciples())
    if error:
        raise HTTPException(status_code=400, detail=error)

    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重试")

    disciple = next(
        (d for d in state.disciples if d.template_id == payload.template_id), None
    )
    return {
        "revision": revision + 1,
        "reputation": state.resources.reputation,
        "disciple": disciple.model_dump(mode="json") if disciple else None,
    }
