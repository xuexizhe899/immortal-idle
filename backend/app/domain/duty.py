"""值守编制与挂机产出速率。

速率计算是纯函数：相同输入必得相同输出，分段结算要按它复算，测试也依赖这一点。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from app.models.save import DiscipleState, DutyEvent, DutySlot, GameState
from app.domain.progression import is_on_run
from app.domain.settle import BASE_MATERIALS_PER_HOUR

MAX_DUTY_SLOTS = 6

# 四倾向到产出的映射；辅倾向同时影响行动力恢复与伤势消退
LEAN_RATES = {
    "attack": ("cultivation_rate",),
    "defense": ("spirit_stone_rate",),
    "support": ("stamina_rate", "injury_rate"),
    "craft": ("material_rate",),
}

# 品质系数与每点境界的附加值，都是加区百分比
RARITY_FACTOR = {1: 0.04, 2: 0.06, 3: 0.09}
REALM_BONUS = 0.01

RATE_KEYS = (
    "cultivation_rate",
    "spirit_stone_rate",
    "stamina_rate",
    "material_rate",
    "injury_rate",
)


@dataclass(frozen=True)
class DutyMember:
    """速率输入：倾向、品质、境界与个人生产加成。"""

    lean: str
    rarity: int
    realm: int
    bonuses: dict[str, float] = field(default_factory=dict)


def compute_rates(members: Iterable[DutyMember]) -> dict[str, float]:
    """把值守弟子折算成五类产出加成（加区，小数）。

    个人丹药只放大该弟子在对应产出上的贡献，不改变全宗门基础速率。
    """
    rates = dict.fromkeys(RATE_KEYS, 0.0)
    for member in members:
        bonus = RARITY_FACTOR.get(member.rarity, 0.0) + member.realm * REALM_BONUS
        for key in LEAN_RATES.get(member.lean, ()):
            rates[key] += bonus * (1 + member.bonuses.get(key, 0.0))
    return rates


def personal_duty_rates(
    disciple: DiscipleState, template: dict, training_level: int = 1,
) -> dict[str, float]:
    """个人倾向与专长贡献；不包含本宗基础收益、羁绊或外宗驻守。"""
    multiplier = 1 + 0.25 * (training_level - 1)
    rates = compute_rates([DutyMember(
        lean=template["lean"], rarity=template["rarity"], realm=disciple.realm,
        bonuses=disciple.bonuses,
    )])
    rates = {key: value * multiplier for key, value in rates.items()}
    specialty = template.get("production_specialty")
    if specialty:
        # 专长不按品质衰减；外宗专材没有本宗基础产量，只能在驻守时增产。
        rates[f"material_{specialty}_flat"] = BASE_MATERIALS_PER_HOUR.get(specialty, 0.0) * multiplier
    return rates


def rates_of(
    state: GameState, templates: dict[str, dict], bonds: dict[str, dict] | None = None,
) -> dict[str, float]:
    """值守倾向、生活专长和驻守共同决定当期速率。"""
    training = 1 + 0.25 * (state.facility_levels.get("training", 1) - 1)
    rates = dict.fromkeys(RATE_KEYS, 0.0)
    by_id = {d.id: d for d in state.disciples}
    active = set()
    for slot in state.duty_slots:
        disciple = by_id.get(slot.disciple_id)
        if disciple is None:
            continue
        active.add(disciple.template_id)
        template = templates.get(disciple.template_id)
        if template:
            for key, value in personal_duty_rates(disciple, template, state.facility_levels.get("training", 1)).items():
                rates[key] = rates.get(key, 0.0) + value
    for bond in (bonds or {}).values():
        if len(active & set(bond["members"])) < bond.get("requires", len(bond["members"])):
            continue
        for effect in bond.get("effects", []):
            if effect["scope"] == "duty" and effect["mode"] == "add_pct":
                rates[effect["stat"]] = rates.get(effect["stat"], 0.0) + effect["value"] * training
    for materials in garrison_production(state, templates).values():
        for material, value in materials.items():
            key = f"material_{material}_flat"
            rates[key] = rates.get(key, 0.0) + value
    return rates


def garrison_production(state: GameState, templates: dict[str, dict]) -> dict[str, dict[str, float]]:
    """每名驻守者独立贡献，匹配对应产物的专长翻倍。"""
    by_id = {disciple.id: disciple for disciple in state.disciples}
    production = {}
    for sect in state.sects:
        if not sect.conquered:
            continue
        materials = {sect.material_id: 0.0, sect.special_material_id: 0.0}
        for slot in sect.garrison:
            disciple = by_id.get(slot.disciple_id)
            if disciple is None or is_on_run(state, disciple):
                continue
            specialty = templates.get(disciple.template_id, {}).get("production_specialty")
            for material, base in ((sect.material_id, 0.5), (sect.special_material_id, 0.15)):
                materials[material] += base * sect.level * (2 if specialty == material else 1)
        production[sect.id] = materials
    return production


def assign(
    state: GameState, disciple_id: str, templates: dict[str, dict], now: datetime,
    bonds: dict[str, dict] | None = None,
) -> str | None:
    """把弟子加入值守编制；成功返回 None，失败返回原因。"""
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return "弟子不存在"
    if disciple.template_id not in templates:
        return "弟子模板未配置"
    if any(slot.disciple_id == disciple_id for slot in state.duty_slots):
        return "该弟子已在值守"
    if len(state.duty_slots) >= MAX_DUTY_SLOTS:
        return f"值守编制已满（{MAX_DUTY_SLOTS} 人）"
    if is_on_run(state, disciple):
        return "该弟子正在出征"

    # 目标本宗岗位校验通过后才从外宗离岗，失败不能丢失原安排。
    for sect in state.sects:
        sect.garrison = [slot for slot in sect.garrison if slot.disciple_id != disciple_id]
    state.duty_slots.append(DutySlot(disciple_id=disciple_id, assigned_at=now))
    record_event(state, templates, now, bonds)
    return None


def unassign(
    state: GameState, disciple_id: str, templates: dict[str, dict], now: datetime,
    bonds: dict[str, dict] | None = None,
) -> str | None:
    """把弟子移出值守编制；成功返回 None，失败返回原因。"""
    remaining = [slot for slot in state.duty_slots if slot.disciple_id != disciple_id]
    if len(remaining) == len(state.duty_slots):
        return "该弟子不在值守"

    state.duty_slots = remaining
    record_event(state, templates, now, bonds)
    return None


def record_event(
    state: GameState, templates: dict[str, dict], now: datetime,
    bonds: dict[str, dict] | None = None,
) -> None:
    """记录一次编制变更事件，供惰性结算按时间段拆分。"""
    state.duty_events.append(
        DutyEvent(at=now, rates=rates_of(state, templates, bonds))
    )
