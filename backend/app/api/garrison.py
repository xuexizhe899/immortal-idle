"""驻守变更先补算旧岗位收益，再原子保存新岗位。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.domain.deployment import assign_garrison, unassign_garrison
from app.models.api import GameSnapshot, RevisionRequest
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/garrison", tags=["garrison"])


class GarrisonRequest(RevisionRequest):
    sect_id: str
    disciple_id: str


@router.post("/assign", response_model=GameSnapshot)
async def assign(slot_id: int, payload: GarrisonRequest, repo: SaveRepository = Depends(get_repo)) -> GameSnapshot:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = assign_garrison(command.state, payload.sect_id, payload.disciple_id, command.settled_at)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return snapshot(command.state, command.revision + 1)


@router.post("/unassign", response_model=GameSnapshot)
async def unassign(slot_id: int, payload: GarrisonRequest, repo: SaveRepository = Depends(get_repo)) -> GameSnapshot:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = unassign_garrison(command.state, payload.sect_id, payload.disciple_id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return snapshot(command.state, command.revision + 1)
