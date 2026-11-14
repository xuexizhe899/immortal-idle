"""炼制命令：丹药炼成入行囊，法器立即提供宗门永久加成。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_recipes
from app.domain.craft import craft, recipe_view
from app.models.api import CraftListResponse, CraftResponse, RevisionRequest
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/craft", tags=["craft"])


class CraftRequest(RevisionRequest):
    recipe_id: str
    quantity: int = Field(default=1, ge=1, strict=True)
    grade: int = Field(default=1, ge=1, le=3, strict=True)


@router.get("", response_model=CraftListResponse)
async def list_recipes(
    slot_id: int, grade: int = Query(default=1, ge=1, le=3),
    repo: SaveRepository = Depends(get_repo),
) -> CraftListResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return CraftListResponse(
        revision=revision,
        recipes=[recipe_view(state, recipe, grade) for recipe in load_recipes().values()],
    )


@router.post("", response_model=CraftResponse)
async def craft_recipe(
    slot_id: int, payload: CraftRequest, repo: SaveRepository = Depends(get_repo),
) -> CraftResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = craft(command.state, payload.recipe_id, load_recipes(), payload.quantity, payload.grade)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return CraftResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        bonuses=command.state.bonuses, inventory=command.state.inventory,
    )
