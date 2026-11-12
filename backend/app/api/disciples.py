"""弟子成长与遗留疗伤物品入口。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_disciples, load_recipes, load_skills, load_weapons
from app.domain import training
from app.domain.items import use_pill
from app.domain.progression import breakthrough, upgrade
from app.models.api import (
    BreakthroughResponse, GameSnapshot, RevisionRequest, TrainingPreview, UpgradeResponse,
)
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/disciples", tags=["disciples"])


def find_disciple(state, disciple_id: str):
    return next((d for d in state.disciples if d.id == disciple_id), None)


@router.get("/{disciple_id}/training", response_model=TrainingPreview)
async def training_preview(
    slot_id: int, disciple_id: str, repo: SaveRepository = Depends(get_repo),
) -> TrainingPreview:
    """只读培养预览；不补算、不扣资源、不改变存档。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, _ = loaded
    disciple = find_disciple(state, disciple_id)
    if disciple is None:
        raise HTTPException(status_code=404, detail="弟子不存在")
    template = load_disciples().get(disciple.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="弟子模板未配置")
    return training.preview(
        state, disciple, template, load_skills(), load_weapons(),
    )


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
    disciple = find_disciple(command.state, disciple_id)
    return UpgradeResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        disciple=disciple, costs=costs,
    )


@router.post("/{disciple_id}/breakthrough", response_model=BreakthroughResponse)
async def breakthrough_disciple(
    slot_id: int, disciple_id: str, payload: RevisionRequest,
    repo: SaveRepository = Depends(get_repo),
) -> BreakthroughResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    costs, error = breakthrough(command.state, disciple_id, load_disciples())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    disciple = find_disciple(command.state, disciple_id)
    return BreakthroughResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        disciple=disciple, costs=costs,
    )


@router.post("/{disciple_id}/heal", response_model=GameSnapshot)
async def heal_disciple(
    slot_id: int, disciple_id: str, payload: RevisionRequest,
    repo: SaveRepository = Depends(get_repo),
) -> GameSnapshot:
    """遗留疗伤入口：与 /items/use 共用规则，优先消耗旧 healing_pill。"""
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = use_pill(
        command.state, disciple_id, "liao_shang_dan",
        load_recipes(), load_disciples(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return snapshot(command.state, command.revision + 1)
