"""地区图层、片区解锁与待迎击进度。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.base import ContractModel as BaseModel


class WorldProgress(BaseModel):
    """跨图层保存征服事实；敌情锚点独立保存，切图层不重置积攒。"""

    current_region: int = Field(default=1, ge=1)
    unlocked_regions: list[int] = Field(default_factory=lambda: [1])
    unlocked_areas: dict[str, int] = Field(default_factory=lambda: {"1": 1})
    cleared_nodes: list[str] = Field(default_factory=list)
    claimed_nodes: list[str] = Field(default_factory=list)
    pending_invasions: dict[str, int] = Field(default_factory=lambda: {"1": 1})
    invasion_waves: dict[str, int] = Field(default_factory=lambda: {"1": 1})
    last_invasion_at: dict[str, datetime] = Field(default_factory=dict)
    tower_records: dict[str, dict[str, int]] = Field(default_factory=dict)


WorldNodeKind = Literal["sect", "dungeon", "gate", "invasion", "raid", "tower"]


class WorldNodeView(BaseModel):
    id: str
    kind: WorldNodeKind
    name: str
    description: str
    region_id: int
    area: int
    x: float
    y: float
    sect_id: str = ""
    locked: bool = False
    reason: str = ""
    cleared: bool = False
    stamina_cost: int = 0
    enemy_scale: float = 1.0
    enemy_ids: list[str] = Field(default_factory=list)
    node_count: int = 1
    gear_tier: int = 1
    gear_slot: str = ""
    rewards: dict[str, float] = Field(default_factory=dict)
    retrial_rewards: dict[str, float] = Field(default_factory=dict)
    wave: int = 0


class AreaView(BaseModel):
    id: int
    name: str
    description: str
    unlocked: bool


class RegionView(BaseModel):
    id: int
    name: str
    subtitle: str
    unlocked: bool
    selected: bool
    palette: str
    enemy_scale: float
    tower_rewards: dict[str, dict[str, float]] = Field(default_factory=dict)
    areas: list[AreaView]
    nodes: list[WorldNodeView]


class InvasionView(BaseModel):
    pending: int
    cap: int
    wave: int
    hours_per_wave: float
    next_at: datetime | None = None
    critical_nodes: list[WorldNodeView] = Field(default_factory=list)


class AscensionView(BaseModel):
    target_region: int | None = None
    token_id: str
    held: int
    can_ascend: bool
    reason: str = ""


class WorldView(BaseModel):
    current_region: int
    regions: list[RegionView]
    invasions: InvasionView
    ascension: AscensionView
