"""四槽装备命令：所有资源、候选与归属在同一次 CAS 中落档。"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_equipment
from app.domain.equipment import (
    equip_gear, gear_views, reforge_gear, resolve_reforge, smelt_gear,
    unequip_gear, upgrade_gear,
)
from app.models.api import GameSnapshot, RevisionRequest
from app.models.base import ContractModel
from app.models.equipment import GearView
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/equipment", tags=["equipment"])


class EquipmentListResponse(ContractModel):
    revision: int
    items: list[GearView]
    slots: dict[str, str]
    material: str
    material_name: str


class EquipmentResponse(GameSnapshot):
    items: list[GearView]
    message: str


class EquipmentRequest(RevisionRequest):
    action: Literal["equip", "unequip", "upgrade", "reforge", "resolve", "smelt", "lock"]
    item_id: str
    disciple_id: str = ""
    keep: bool = False
    locked: bool = False


@router.get("", response_model=EquipmentListResponse)
async def list_equipment(
    slot_id: int, repo: SaveRepository = Depends(get_repo),
) -> EquipmentListResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    config = load_equipment()
    return EquipmentListResponse(
        revision=revision, items=gear_views(state, config), slots=config["slots"],
        material=config["material"], material_name=config["material_name"],
    )


@router.post("", response_model=EquipmentResponse)
async def equipment_command(
    slot_id: int, payload: EquipmentRequest, repo: SaveRepository = Depends(get_repo),
) -> EquipmentResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    state, config = command.state, load_equipment()
    if payload.action == "equip":
        error = equip_gear(state, payload.item_id, payload.disciple_id)
    elif payload.action == "unequip":
        error = unequip_gear(state, payload.item_id)
    elif payload.action == "upgrade":
        error = upgrade_gear(state, payload.item_id, config)
    elif payload.action == "reforge":
        error = reforge_gear(state, payload.item_id, config)
    elif payload.action == "resolve":
        error = resolve_reforge(state, payload.item_id, payload.keep)
    elif payload.action == "smelt":
        error = smelt_gear(state, payload.item_id, config)
    else:
        item = state.gear.get(payload.item_id)
        error = "装备不存在" if item is None else None
        if item is not None:
            item.locked = payload.locked
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    messages = {
        "equip": "装备已穿戴", "unequip": "装备已卸下", "upgrade": "装备强化成功",
        "reforge": "洗练结果已生成，请选择保留或替换", "resolve": "洗练结果已确认",
        "smelt": "装备已熔炼，材料已收入行囊", "lock": "装备锁定已更新",
    }
    return EquipmentResponse(
        **snapshot(state, command.revision + 1).model_dump(),
        items=gear_views(state, config), message=messages[payload.action],
    )
