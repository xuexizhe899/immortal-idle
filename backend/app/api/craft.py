"""炼制接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.saves import get_repo
from app.config_loader import load_recipes
from app.domain.craft import craft
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/craft", tags=["craft"])


class CraftRequest(BaseModel):
    """炼制请求；heal / realm 类配方需要 target。"""

    recipe_id: str
    target: str | None = None


@router.post("")
async def craft_recipe(
    slot_id: int, payload: CraftRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """消耗材料炼制一件配方。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded

    error = craft(state, payload.recipe_id, payload.target, load_recipes())
    if error:
        raise HTTPException(status_code=400, detail=error)

    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重试")

    return {
        "revision": revision + 1,
        "bonuses": state.bonuses,
        "inventory": state.inventory,
    }
