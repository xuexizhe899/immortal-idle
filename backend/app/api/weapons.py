"""专属武器命令：锻造、装备与卸下都携带 revision 并由服务端校验归属。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_disciples, load_materials, load_weapons
from app.domain.weapons import (
    craft_weapon, equip_weapon, unequip_weapon, upgrade_weapon, weapon_views,
)
from app.models.api import (
    RevisionRequest, WeaponCommandResponse, WeaponListResponse,
)
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/weapons", tags=["weapons"])


class CraftWeaponRequest(RevisionRequest):
    weapon_id: str


class EquipWeaponRequest(RevisionRequest):
    weapon_id: str
    disciple_id: str


class UnequipWeaponRequest(RevisionRequest):
    disciple_id: str


def list_weapons(state) -> list:
    """按当前存档归属生成专武列表。"""
    return weapon_views(
        state, load_weapons(), load_disciples(), load_materials(),
    )


@router.get("", response_model=WeaponListResponse)
async def get_weapons(
    slot_id: int, repo: SaveRepository = Depends(get_repo),
) -> WeaponListResponse:
    """只读专武列表；不补算、不扣材料、不改变存档。"""
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return WeaponListResponse(revision=revision, weapons=list_weapons(state))


@router.post("/craft", response_model=WeaponCommandResponse)
async def craft(
    slot_id: int, payload: CraftWeaponRequest, repo: SaveRepository = Depends(get_repo),
) -> WeaponCommandResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = craft_weapon(
        command.state, payload.weapon_id,
        load_weapons(), load_disciples(), load_materials(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return WeaponCommandResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        weapons=list_weapons(command.state),
    )


@router.post("/equip", response_model=WeaponCommandResponse)
async def equip(
    slot_id: int, payload: EquipWeaponRequest, repo: SaveRepository = Depends(get_repo),
) -> WeaponCommandResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = equip_weapon(
        command.state, payload.weapon_id, payload.disciple_id, load_weapons(),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return WeaponCommandResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        weapons=list_weapons(command.state),
    )


@router.post("/unequip", response_model=WeaponCommandResponse)
async def unequip(
    slot_id: int, payload: UnequipWeaponRequest, repo: SaveRepository = Depends(get_repo),
) -> WeaponCommandResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = unequip_weapon(command.state, payload.disciple_id, load_weapons())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return WeaponCommandResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        weapons=list_weapons(command.state),
    )


@router.post("/upgrade", response_model=WeaponCommandResponse)
async def upgrade(
    slot_id: int, payload: CraftWeaponRequest, repo: SaveRepository = Depends(get_repo),
) -> WeaponCommandResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = upgrade_weapon(command.state, payload.weapon_id, load_weapons())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return WeaponCommandResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        weapons=list_weapons(command.state),
    )
