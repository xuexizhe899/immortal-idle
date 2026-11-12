"""招募命令：声望解锁新弟子；已拥有角色的境界提升走培养命令。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_disciples
from app.domain.recruit import recruit
from app.models.api import RecruitResponse, RevisionRequest
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/recruit", tags=["recruit"])


class RecruitRequest(RevisionRequest):
    template_id: str


@router.post("", response_model=RecruitResponse)
async def recruit_disciple(
    slot_id: int, payload: RecruitRequest, repo: SaveRepository = Depends(get_repo),
) -> RecruitResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = recruit(command.state, payload.template_id, load_disciples())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    disciple = next(d for d in command.state.disciples if d.template_id == payload.template_id)
    return RecruitResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        reputation=command.state.resources.reputation, disciple=disciple,
    )
