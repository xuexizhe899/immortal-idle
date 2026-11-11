"""弟子成长与遗留疗伤丹物品入口。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.domain.injuries import heal
from app.domain.progression import is_on_run, upgrade
from app.models.api import GameSnapshot, RevisionRequest, UpgradeResponse
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/disciples", tags=["disciples"])
HEALING_PILL = "healing_pill"


@router.post("/{disciple_id}/upgrade", response_model=UpgradeResponse)
async def upgrade_disciple(
    slot_id: int, disciple_id: str, payload: RevisionRequest,
    repo: SaveRepository = Depends(get_repo),
) -> UpgradeResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    costs, error = upgrade(command.state, disciple_id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    disciple = next(d for d in command.state.disciples if d.id == disciple_id)
    return UpgradeResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        disciple=disciple, costs=costs,
    )


@router.post("/{disciple_id}/heal", response_model=GameSnapshot)
async def heal_disciple(
    slot_id: int, disciple_id: str, payload: RevisionRequest,
    repo: SaveRepository = Depends(get_repo),
) -> GameSnapshot:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    disciple = next((d for d in command.state.disciples if d.id == disciple_id), None)
    if disciple is None:
        raise HTTPException(status_code=404, detail="弟子不存在")
    if is_on_run(command.state, disciple):
        raise HTTPException(status_code=400, detail="出征中的弟子暂不可疗伤")
    if command.state.inventory.get(HEALING_PILL, 0) < 1:
        raise HTTPException(status_code=400, detail="疗伤丹不足")
    command.state.inventory[HEALING_PILL] -= 1
    if not command.state.inventory[HEALING_PILL]:
        del command.state.inventory[HEALING_PILL]
    heal(disciple)
    await commit_mutation(slot_id, command, repo)
    return snapshot(command.state, command.revision + 1)
