"""值守接口：变更前按旧速率补算，返回完整权威快照。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_bonds, load_disciples
from app.domain.duty import assign, member_garrison_rates, personal_duty_rates, rates_of, unassign
from app.domain.progression import is_on_run
from app.models.api import AssignmentListResponse, AssignmentView, DutyResponse, RevisionRequest
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


@router.get("/assignments", response_model=AssignmentListResponse)
async def assignments(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> AssignmentListResponse:
    """只读分配预览：岗位与个人产出潜力，不补算、不写回。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    templates = load_disciples()
    training = state.facility_levels.get("training", 1)
    duty_ids = {slot.disciple_id for slot in state.duty_slots}
    garrison_of = {slot.disciple_id: sect for sect in state.sects for slot in sect.garrison}
    views = []
    for disciple in state.disciples:
        template = templates.get(disciple.template_id, {})
        sect = garrison_of.get(disciple.id)
        post = "run" if is_on_run(state, disciple) else "duty" if disciple.id in duty_ids else "garrison" if sect else "idle"
        views.append(AssignmentView(
            disciple_id=disciple.id, post=post, sect_id=sect.id if sect else None,
            duty_rates=personal_duty_rates(disciple, template, training),
            garrison_rates=member_garrison_rates(sect, disciple, template) if post == "garrison" and sect else {},
        ))
    return AssignmentListResponse(revision=revision, assignments=views)


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
