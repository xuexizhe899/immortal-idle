"""出征命令：revision 防重放，战斗与资源由服务端结算。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot, status_of
from app.config_loader import load_affixes, load_bonds, load_disciples, load_modes
from app.domain import run_engine
from app.models.api import RevisionRequest, RunResponse, RunSettleResponse
from app.models.save import GameState
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/run", tags=["run"])
ENDED = {"defeated", "cleared"}


class StartRunRequest(RevisionRequest):
    party: list[str]


class ChooseRequest(RevisionRequest):
    choice: int


class AffixRequest(RevisionRequest):
    affix_id: str


def run_payload(state: GameState, revision: int) -> RunResponse:
    return RunResponse(
        **snapshot(state, revision).model_dump(), run=state.active_run,
        battle_result=state.active_run.last_battle if state.active_run else None,
    )


@router.get("", response_model=RunResponse)
async def get_run(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> RunResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return run_payload(*loaded)


@router.post("/start", response_model=RunResponse)
async def start(
    slot_id: int, payload: StartRunRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = run_engine.start_run(
        command.state, payload.party, load_disciples(), load_modes()["tower"], command.settled_at,
        bonds=load_bonds(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await repo.snapshot(slot_id, "before_run")
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/choose", response_model=RunResponse)
async def choose_node(
    slot_id: int, payload: ChooseRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = run_engine.choose(
        command.state, payload.choice, load_disciples(), load_affixes(),
        load_modes()["tower"], load_bonds(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/affix", response_model=RunResponse)
async def pick_affix(
    slot_id: int, payload: AffixRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = run_engine.pick_affix(command.state, payload.affix_id, load_modes()["tower"])
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/settle", response_model=RunSettleResponse)
async def settle(
    slot_id: int, payload: RevisionRequest, repo: SaveRepository = Depends(get_repo),
) -> RunSettleResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    if command.state.active_run is None:
        raise HTTPException(status_code=400, detail="没有进行中的出征")
    if status_of(command.state) not in ENDED:
        raise HTTPException(status_code=400, detail="出征尚未结束")
    result = run_engine.settle_run(command.state, load_modes()["tower"], command.settled_at)
    await commit_mutation(slot_id, command, repo)
    return RunSettleResponse(**snapshot(command.state, command.revision + 1).model_dump(), **result)
