"""前端展示与命令响应的类型契约，统一由 OpenAPI 生成。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.base import ContractModel as BaseModel

from app.models.save import ActiveRun, BattleSummary, DiscipleState, DutySlot, GameState

RunStatus = Literal["idle", "choosing_node", "choosing_affix", "defeated", "cleared"]


class RevisionRequest(BaseModel):
    revision: int = Field(ge=1)


class ProductionCatalog(BaseModel):
    cultivation: float
    spirit_stone: float
    stamina: float
    materials: dict[str, float]
    injury_recovery_multiplier: float = 1.0


class GameSnapshot(BaseModel):
    revision: int
    state: GameState
    status: RunStatus
    production: ProductionCatalog


class RunResponse(GameSnapshot):
    run: ActiveRun | None = None
    battle_result: BattleSummary | None = None


class RunSettleResponse(GameSnapshot):
    cleared: int
    victory: bool
    loot: dict[str, float]


class RecruitResponse(GameSnapshot):
    reputation: float
    disciple: DiscipleState


class CraftResponse(GameSnapshot):
    bonuses: dict[str, float]
    inventory: dict[str, int]


class DutyResponse(GameSnapshot):
    duty: list[DutySlot]
    rates: dict[str, float]


class UpgradeResponse(GameSnapshot):
    disciple: DiscipleState
    costs: dict[str, float]


class SettleGains(BaseModel):
    cultivation: float
    spirit_stone: float
    stamina: float
    materials: dict[str, int] = Field(default_factory=dict)


class SettleResponse(GameSnapshot):
    elapsed_hours: float
    dropped_hours: float
    gained: SettleGains
    warnings: list[str]


class Effect(BaseModel):
    stat: str
    mode: str
    value: float
    scope: str


class DiscipleCatalog(BaseModel):
    name: str
    title: str = ""
    lean: str
    rarity: int
    origin: str = ""
    asset_id: str
    base_stats: dict[str, float]
    skill: str
    passive: str
    bonds: list[str] = Field(default_factory=list)
    unlock_cost: dict[str, float] = Field(default_factory=dict)


class AffixCatalog(BaseModel):
    name: str
    group: str
    group_name: str
    effects: list[Effect] = Field(default_factory=list)


class RecipeCatalog(BaseModel):
    name: str
    kind: str
    inputs: dict[str, int]
    special: str | None = None
    effects: list[Effect] = Field(default_factory=list)


class BondCatalog(BaseModel):
    name: str
    members: list[str]
    requires: int
    effects: list[Effect] = Field(default_factory=list)


class SkillCatalog(BaseModel):
    name: str
    type: str
    description: str = ""
    effects: list[Effect] = Field(default_factory=list)
    implemented: bool = False


class CityHotspot(BaseModel):
    id: str
    name: str
    panel: str
    x: float
    y: float
    w: float
    h: float
    sprite: str | None = None
    anim: str | None = None


class CityLayout(BaseModel):
    background: str
    aspect: float
    hotspots: list[CityHotspot]


class ModeCatalog(BaseModel):
    id: str
    name: str
    node_count: int
    stamina_cost: float
    boss_every: int
    defeat_ratio: float
    start_hp: int


class RulesCatalog(BaseModel):
    max_party: int
    max_duty: int
    idle_cap_hours: float
    injury_attack_penalty: float
    injury_hours_per_stack: float
    max_injury_stacks: int
    injured_can_run: bool = True
    level_growth: float
    realm_growth: float
    upgrade_cultivation_base: float
    upgrade_spirit_stone_base: float
    craft_applies_immediately: bool = True


class CatalogResponse(BaseModel):
    disciples: dict[str, DiscipleCatalog]
    affixes: dict[str, AffixCatalog]
    recipes: dict[str, RecipeCatalog]
    materials: dict[str, str]
    bonds: dict[str, BondCatalog]
    skills: dict[str, SkillCatalog]
    mode: ModeCatalog
    rules: RulesCatalog
    production: ProductionCatalog
    city: CityLayout
