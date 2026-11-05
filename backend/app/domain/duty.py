"""值守编制与挂机产出速率。

速率计算是纯函数：相同输入必得相同输出，分段结算要按它复算，测试也依赖这一点。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.models.save import DiscipleState, DutyEvent, DutySlot, GameState

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
    """速率输入：只取影响产出的字段。"""

    lean: str
    rarity: int
    realm: int


def compute_rates(members: Iterable[DutyMember]) -> dict[str, float]:
    """把值守弟子折算成五类产出加成（加区，小数）。"""
    rates = dict.fromkeys(RATE_KEYS, 0.0)
    for member in members:
        bonus = RARITY_FACTOR.get(member.rarity, 0.0) + member.realm * REALM_BONUS
        for key in LEAN_RATES.get(member.lean, ()):
            rates[key] += bonus
    return rates


def members_of(state: GameState, templates: dict[str, dict]) -> list[DutyMember]:
    """按编制里的弟子 id 取出速率输入，模板缺失的跳过。"""
    by_id: dict[str, DiscipleState] = {d.id: d for d in state.disciples}
    members: list[DutyMember] = []
    for slot in state.duty_slots:
        disciple = by_id.get(slot.disciple_id)
        if disciple is None:
            continue
        template = templates.get(disciple.template_id)
        if template is None:
            continue
        members.append(
            DutyMember(
                lean=template["lean"],
                rarity=template["rarity"],
                realm=disciple.realm,
            )
        )
    return members


def assign(
    state: GameState, disciple_id: str, templates: dict[str, dict], now: datetime
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
    if disciple.busy:
        return "该弟子正在出征"

    state.duty_slots.append(DutySlot(disciple_id=disciple_id, assigned_at=now))
    record_event(state, templates, now)
    return None


def unassign(
    state: GameState, disciple_id: str, templates: dict[str, dict], now: datetime
) -> str | None:
    """把弟子移出值守编制；成功返回 None，失败返回原因。"""
    remaining = [slot for slot in state.duty_slots if slot.disciple_id != disciple_id]
    if len(remaining) == len(state.duty_slots):
        return "该弟子不在值守"

    state.duty_slots = remaining
    record_event(state, templates, now)
    return None


def record_event(state: GameState, templates: dict[str, dict], now: datetime) -> None:
    """记录一次编制变更事件，供惰性结算按时间段拆分。"""
    state.duty_events.append(
        DutyEvent(at=now, rates=compute_rates(members_of(state, templates)))
    )
