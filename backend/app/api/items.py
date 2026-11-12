"""物品命令：丹药由独立命令指定弟子服用，失败不扣库存。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_disciples, load_recipes
from app.domain.items import canonical_pill_id, use_pill
from app.models.api import RevisionRequest, UseItemResponse
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/items", tags=["items"])


class UseItemRequest(RevisionRequest):
    item_id: str
    target: str


@router.post("/use", response_model=UseItemResponse)
async def use_item(
    slot_id: int, payload: UseItemRequest, repo: SaveRepository = Depends(get_repo),
) -> UseItemResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = use_pill(
        command.state, payload.target, payload.item_id,
        load_recipes(), load_disciples(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    disciple = next(d for d in command.state.disciples if d.id == payload.target)
    return UseItemResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        disciple=disciple, item_id=canonical_pill_id(payload.item_id),
    )
