"""值守接口：变更前按旧速率补算，返回完整权威快照。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_bonds, load_disciples
from app.domain.duty import assign, rates_of, unassign
from app.models.api import DutyResponse, RevisionRequest
from app.models.save import GameState
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/duty", tags=["duty"])


class DutyChangeRequest(RevisionRequest):
    disciple_id: str


def duty_payload(state: GameState, revision: int) -> DutyResponse:
    return DutyResponse(
        **snapshot(state, revision).model_dump(), duty=state.duty_slots,
        rates=rates_of(state, load_disciples(), load_bonds()),
    )


async def change_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository, join: bool,
) -> DutyResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    change = assign if join else unassign
    error = change(
        command.state, payload.disciple_id, load_disciples(), command.settled_at, load_bonds(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return duty_payload(command.state, command.revision + 1)


@router.get("", response_model=DutyResponse)
async def get_duty(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> DutyResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return duty_payload(*loaded)


@router.post("/assign", response_model=DutyResponse)
async def assign_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository = Depends(get_repo),
) -> DutyResponse:
    return await change_duty(slot_id, payload, repo, join=True)


@router.post("/unassign", response_model=DutyResponse)
async def unassign_duty(
    slot_id: int, payload: DutyChangeRequest, repo: SaveRepository = Depends(get_repo),
) -> DutyResponse:
    return await change_duty(slot_id, payload, repo, join=False)
