"""出征命令：revision 防重放，战斗与资源由服务端结算。"""

from typing import Literal
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot, status_of
from app.config_loader import load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_sects, load_skills, load_weapons
from app.domain import conquest, run_engine
from app.models.api import RevisionRequest, RunResponse, RunSettleResponse
from app.models.save import GameState
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/run", tags=["run"])
ENDED = {"defeated", "cleared"}


class StartRunRequest(RevisionRequest):
    party: list[str]
    mode: Literal["tower", "expedition"] = "tower"
    sect_id: str | None = None
    tower_tier: int = Field(default=1, ge=1, le=3)


class ArenaRequest(RevisionRequest):
    party: list[str] = Field(min_length=3, max_length=3)


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
    modes = load_modes()
    mode = modes.get(payload.mode)
    if not mode or not mode.get("enabled"):
        raise HTTPException(status_code=400, detail="该远行模式尚未开放")
    sect = None
    if payload.mode == "expedition":
        conquest.ensure_sects(command.state, load_sects(), load_enemies())
        sect = next((item for item in command.state.sects if item.id == payload.sect_id), None)
        if sect is None:
            raise HTTPException(status_code=400, detail="请先选择要征讨的宗门")
    elif payload.sect_id is not None:
        raise HTTPException(status_code=400, detail="问道塔不接受宗门目标")
    error = run_engine.start_run(
        command.state, payload.party, load_disciples(), mode, command.settled_at,
        seed=secrets.randbits(63), bonds=load_bonds(), skills=load_skills(), enemies=load_enemies(),
        affix_pool=load_affixes(), weapons=load_weapons(), route_version=2,
        sect=sect, tower_tier=payload.tower_tier,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await repo.snapshot(slot_id, "before_run")
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/arena", response_model=RunResponse)
async def fight_arena(
    slot_id: int, payload: ArenaRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = conquest.arena(command.state, payload.party)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/retreat", response_model=RunResponse)
async def retreat(
    slot_id: int, payload: RevisionRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = conquest.retreat(command.state)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/choose", response_model=RunResponse)
async def choose_node(
    slot_id: int, payload: ChooseRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = run_engine.choose(command.state, payload.choice)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)


@router.post("/affix", response_model=RunResponse)
async def pick_affix(
    slot_id: int, payload: AffixRequest, repo: SaveRepository = Depends(get_repo),
) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = run_engine.pick_affix(command.state, payload.affix_id)
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
    # 已出发的奖励与结束条件由本局快照决定；实时模式关闭或移除不阻止带回战利品。
    mode = command.state.active_run.party_snapshot.mode
    result = run_engine.settle_run(command.state, mode, command.settled_at)
    await commit_mutation(slot_id, command, repo)
    return RunSettleResponse(**snapshot(command.state, command.revision + 1).model_dump(), **result)
