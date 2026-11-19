"""普通装备实例：随机结果与强化投入均随存档保存。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.models.base import ContractModel

EquipmentSlot = Literal["weapon", "armor", "boots", "ring"]
PositiveCount = Annotated[int, Field(ge=0)]


class GearAffix(ContractModel):
    stat: str
    grade: int = Field(ge=1, le=3)
    value: float = Field(ge=0)


class GearItem(ContractModel):
    id: str
    definition_id: str
    name: str
    slot: EquipmentSlot
    tier: int = Field(default=1, ge=1)
    level: int = Field(default=0, ge=0)
    main_stat: str
    main_value: float = Field(ge=0)
    growth_per_level: float = Field(default=0.1, ge=0)
    affix: str = ""
    affix_grade: int = Field(default=1, ge=1, le=3)
    affix_value: float = Field(default=0, ge=0)
    extra_stats: dict[str, float] = Field(default_factory=dict)
    pending_affix: GearAffix | None = None
    invested: dict[str, PositiveCount] = Field(default_factory=dict)
    locked: bool = False
    source: str = "drop"


class GearView(GearItem):
    stats: dict[str, float] = Field(default_factory=dict)
    equipped_by: str | None = None
    max_level: int = 0
    equip_reason: str = ""
    unequip_reason: str = ""
    upgrade_costs: dict[str, int] = Field(default_factory=dict)
    upgrade_stats: dict[str, float] = Field(default_factory=dict)
    upgradeable: bool = False
    upgrade_reason: str = ""
    reforge_costs: dict[str, int] = Field(default_factory=dict)
    reforge_reason: str = ""
    resolve_reason: str = ""
    smelt_returns: dict[str, int] = Field(default_factory=dict)
    smelt_reason: str = ""
    lock_reason: str = ""
