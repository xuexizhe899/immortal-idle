"""地图命令复用原有出征、岗位与CAS流程；浏览不推进时间或发放奖励。"""

from copy import deepcopy
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.api.run import run_payload
from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_sects, load_skills, load_weapons, load_world
from app.domain import run_engine, world
from app.models.api import GameSnapshot, RevisionRequest, RunResponse
from app.models.world import WorldView
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/world", tags=["world"])


class WorldResponse(GameSnapshot):
    world: WorldView


class TravelRequest(RevisionRequest):
    region_id: int = Field(ge=1)


class WorldStartRequest(RevisionRequest):
    node_id: str
    party: list[str] = Field(min_length=1, max_length=6)
    practice: bool = False
    tower_tier: int = Field(default=1, ge=1, le=3)


def world_payload(state, revision: int) -> WorldResponse:
    config = load_world()
    view = world.world_view(state, config)
    scales = {region["id"]: region["reward_scale"] for region in config["regions"]}
    sects = {sect.id: sect for sect in state.sects}
    styles = {style["name"]: style for style in load_sects()["styles"]}
    tower = load_modes()["tower"]
    # 预览使用与出发相同的静态奖励与地区倍率，客户端无需猜测跨区收益。
    for region in view.regions:
        scale = scales[region.id]
        region.tower_rewards = {
            kind: {key: value * scale for key, value in reward.items()}
            for kind, reward in tower["rewards"].items()
        }
        for node in region.nodes:
            sect = sects.get(node.sect_id)
            if sect is not None:
                node.retrial_rewards = {
                    key: value * scale for key, value in styles.get(sect.style, {}).get("retrial_reward", {}).items()
                }
    return WorldResponse(**snapshot(state, revision).model_dump(), world=view)


@router.get("", response_model=WorldResponse)
async def get_world(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> WorldResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return world_payload(*loaded)


@router.post("/travel", response_model=WorldResponse)
async def travel(slot_id: int, payload: TravelRequest, repo: SaveRepository = Depends(get_repo)) -> WorldResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = world.travel_region(command.state, payload.region_id, command.settled_at, load_world())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return world_payload(command.state, command.revision + 1)


@router.post("/ascend", response_model=WorldResponse)
async def ascend(slot_id: int, payload: RevisionRequest, repo: SaveRepository = Depends(get_repo)) -> WorldResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = world.ascend(command.state, command.settled_at, load_world())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return world_payload(command.state, command.revision + 1)


@router.post("/start", response_model=RunResponse)
async def start(slot_id: int, payload: WorldStartRequest, repo: SaveRepository = Depends(get_repo)) -> RunResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    node, error = world.prepare_world_node(command.state, payload.node_id, load_world(), payload.practice)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if node["kind"] == "sect":
        raise HTTPException(status_code=400, detail="宗门请从征讨或论道入口出发")
    if payload.practice and node["kind"] not in {"raid", "invasion", "gate"}:
        raise HTTPException(status_code=400, detail="仅迎击与守关支持无奖励演练")
    mode = world.tower_mode(command.state, load_modes()["tower"], load_world()) if node["kind"] == "tower" else deepcopy(load_modes()["tower"])
    mode.update(node["mode_overrides"])
    mode.update(
        id="tower" if node["kind"] == "tower" else "dungeon" if node["kind"] == "dungeon" else "world",
        world_node=node, gear_tier=node["gear_tier"], gear_slot=node["gear_slot"],
        opportunities=node["kind"] == "dungeon" and not payload.practice,
    )
    error = run_engine.start_run(
        command.state, payload.party, load_disciples(), mode, command.settled_at,
        seed=secrets.randbits(63), bonds=load_bonds(), skills=load_skills(), enemies=load_enemies(),
        affix_pool=load_affixes() if node["kind"] in {"dungeon", "tower"} else [],
        weapons=load_weapons(), route_version=2, tower_tier=payload.tower_tier,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    command.state.active_run.world_node_id = node["id"]
    command.state.active_run.practice = payload.practice
    await repo.snapshot(slot_id, "before_run")
    await commit_mutation(slot_id, command, repo)
    return run_payload(command.state, command.revision + 1)
