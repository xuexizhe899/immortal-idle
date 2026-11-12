"""自动战斗的固定输入与服务端战报契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from app.models.base import ContractModel as BaseModel

Condition = Literal["always", "shielded", "target_weakened", "first_round"]


class BattleAction(BaseModel):
    kind: Literal["damage", "heal", "shield", "buff"]
    target: Literal["enemy_first", "enemy_lowest", "all_enemies", "ally_lowest", "all_allies", "self", "ally_template"]
    count: int = Field(default=1, ge=1, le=6)
    coefficient: float = Field(default=1, ge=0, le=10)
    duration: int = Field(default=2, ge=1, le=20)
    stat: Literal["atk", "def", "spd"] = "atk"
    value: float = Field(default=0, ge=-.5, le=1)
    target_template: str | None = None


class SkillDefinition(BaseModel):
    id: str
    name: str
    type: Literal["active", "passive"]
    description: str = ""
    effects: list[dict] = Field(default_factory=list)
    cooldown: int = Field(default=3, ge=1, le=20)
    vfx: str = "strike"
    actions: list[BattleAction] = Field(default_factory=list, max_length=4)
    bonuses: dict[str, float] = Field(default_factory=dict)
    condition: Condition = "always"


class BondModifier(BaseModel):
    skill: str
    condition: Condition = "always"
    add_targets: int = Field(default=0, ge=0, le=5)
    coefficient_bonus: float = Field(default=0, ge=0, le=1)
    duration_bonus: int = Field(default=0, ge=0, le=5)
    extra_actions: list[BattleAction] = Field(default_factory=list, max_length=3)


class BattleBond(BaseModel):
    id: str
    name: str
    members: list[str]
    requires: int
    modifiers: list[BondModifier] = Field(default_factory=list)


class BattleUnit(BaseModel):
    """出发固化的角色属性和技能，不引用永久层或当前配置。"""

    model_config = ConfigDict(frozen=True)
    id: str
    template_id: str
    name: str
    asset_id: str = ""
    slot: int = Field(default=0, ge=0, le=5)
    attack: float
    defense: float
    health: int
    speed: float
    active: SkillDefinition
    passive: SkillDefinition


class BattleStatus(BaseModel):
    source: str
    kind: Literal["buff", "shield"]
    stat: str = ""
    value: float = 0
    remaining: int = 0
    expires_round: int


class BattleUnitState(BaseModel):
    id: str
    template_id: str
    name: str
    side: Literal["ally", "enemy"]
    slot: int
    asset_id: str = ""
    hp: int
    max_hp: int
    shield: int = 0
    attack: float
    defense: float
    speed: float
    cooldown: int = 0
    statuses: list[BattleStatus] = Field(default_factory=list)


class BattleEffectResult(BaseModel):
    target_id: str
    kind: Literal["damage", "heal", "shield", "buff"]
    amount: int = 0
    absorbed: int = 0
    hp_after: int
    shield_after: int
    stat: str = ""
    value: float = 0
    source: str


class BattleEvent(BaseModel):
    sequence: int
    round: int
    actor_id: str
    skill_id: str
    skill_name: str
    vfx: str
    bonds: list[str] = Field(default_factory=list)
    effects: list[BattleEffectResult] = Field(default_factory=list)
    units: list[BattleUnitState] = Field(default_factory=list)


class EnemyDefinition(BaseModel):
    id: str
    name: str
    base_stats: dict[str, float]
    skill: SkillDefinition | None = None
    passive: SkillDefinition | None = None
