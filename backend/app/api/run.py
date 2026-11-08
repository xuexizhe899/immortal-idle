"""出征接口：查看、开始、选节点、选词条、结算。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.saves import get_repo
from app.config_loader import load_affixes, load_bonds, load_disciples, load_modes
from app.domain import run_engine
from app.models.save import GameState
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/run", tags=["run"])

ENDED = {"defeated", "cleared"}


class StartRunRequest(BaseModel):
    """出发请求：上阵弟子 id。"""

    party: list[str]


class ChooseRequest(BaseModel):
    """选择第几个候选节点。"""

    choice: int


class AffixRequest(BaseModel):
    """选择哪个词条。"""

    affix_id: str


def utcnow() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def tower_mode() -> dict:
    """取爬塔模式配置；缺失会直接抛 KeyError，说明配置没铺。"""
    return load_modes()["tower"]


def run_payload(state: GameState, revision: int, mode: dict) -> dict:
    """把出征状态打包成接口返回结构。"""
    run = state.active_run
    return {
        "revision": revision,
        "status": run_engine.run_status(run, mode) if run else "idle",
        "run": run.model_dump(mode="json") if run else None,
    }


async def load_slot(slot_id: int, repo: SaveRepository) -> tuple[GameState, int]:
    """读取存档；不存在直接返回 404。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return loaded


async def commit(slot_id: int, state: GameState, revision: int, repo: SaveRepository) -> None:
    """CAS 写回；冲突返回 409 让调用方重试。"""
    if not await repo.save_state(slot_id, state, revision):
        raise HTTPException(status_code=409, detail="revision 冲突，请重试")


@router.get("")
async def get_run(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """查看当前出征状态。"""
    state, revision = await load_slot(slot_id, repo)
    return run_payload(state, revision, tower_mode())


@router.post("/start")
async def start(
    slot_id: int, payload: StartRunRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """开始一次出征。"""
    state, revision = await load_slot(slot_id, repo)
    mode = tower_mode()
    error = run_engine.start_run(state, payload.party, load_disciples(), mode, utcnow())
    if error:
        raise HTTPException(status_code=400, detail=error)

    await commit(slot_id, state, revision, repo)
    return run_payload(state, revision + 1, mode)


@router.post("/choose")
async def choose_node(
    slot_id: int, payload: ChooseRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """选择节点并自动战斗。"""
    state, revision = await load_slot(slot_id, repo)
    mode = tower_mode()
    error = run_engine.choose(
        state, payload.choice, load_disciples(), load_affixes(), mode, load_bonds()
    )
    if error:
        raise HTTPException(status_code=400, detail=error)

    await commit(slot_id, state, revision, repo)
    return run_payload(state, revision + 1, mode)


@router.post("/affix")
async def pick_affix(
    slot_id: int, payload: AffixRequest, repo: SaveRepository = Depends(get_repo)
) -> dict:
    """选择一个词条并进入下一层。"""
    state, revision = await load_slot(slot_id, repo)
    mode = tower_mode()
    error = run_engine.pick_affix(state, payload.affix_id, mode)
    if error:
        raise HTTPException(status_code=400, detail=error)

    await commit(slot_id, state, revision, repo)
    return run_payload(state, revision + 1, mode)


@router.post("/settle")
async def settle(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> dict:
    """结算出征并写回收益。"""
    state, revision = await load_slot(slot_id, repo)
    mode = tower_mode()
    if state.active_run is None:
        raise HTTPException(status_code=400, detail="没有进行中的出征")
    if run_engine.run_status(state.active_run, mode) not in ENDED:
        raise HTTPException(status_code=400, detail="出征尚未结束")

    result = run_engine.settle_run(state, mode, utcnow())
    await commit(slot_id, state, revision, repo)
    return {"revision": revision + 1, **result, "state": state.model_dump(mode="json")}
