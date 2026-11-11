"""炼制命令：配方效果立即生效，服务端先结算旧产出。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_recipes
from app.domain.craft import craft
from app.models.api import CraftResponse, RevisionRequest
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/craft", tags=["craft"])


class CraftRequest(RevisionRequest):
    recipe_id: str
    target: str | None = None


@router.post("", response_model=CraftResponse)
async def craft_recipe(
    slot_id: int, payload: CraftRequest, repo: SaveRepository = Depends(get_repo),
) -> CraftResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = craft(command.state, payload.recipe_id, payload.target, load_recipes())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return CraftResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        bonuses=command.state.bonuses, inventory=command.state.inventory,
    )
