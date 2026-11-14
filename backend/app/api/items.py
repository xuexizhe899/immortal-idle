"""物品命令：丹药由独立命令指定弟子服用，失败不扣库存。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.models.base import ContractModel

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_disciples, load_recipes
from app.domain.items import canonical_pill_id, heal_party, heal_party_preview, use_pill
from app.models.api import HealPartyPreview, HealPartyResponse, RevisionRequest, UseItemResponse
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


class HealPartyPreviewRequest(ContractModel):
    party: list[str] = Field(min_length=1, max_length=6)


class HealPartyRequest(RevisionRequest):
    party: list[str] = Field(min_length=1, max_length=6)


@router.post("/heal-party/preview", response_model=HealPartyPreview)
async def preview_healing(
    slot_id: int, payload: HealPartyPreviewRequest, repo: SaveRepository = Depends(get_repo),
) -> HealPartyPreview:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return HealPartyPreview(revision=revision, **heal_party_preview(state, payload.party, load_recipes()))


@router.post("/heal-party", response_model=HealPartyResponse)
async def heal_team(
    slot_id: int, payload: HealPartyRequest, repo: SaveRepository = Depends(get_repo),
) -> HealPartyResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    result = heal_party(command.state, payload.party, load_recipes())
    if result["reason"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    await commit_mutation(slot_id, command, repo)
    return HealPartyResponse(**snapshot(command.state, command.revision + 1).model_dump(), **result)
