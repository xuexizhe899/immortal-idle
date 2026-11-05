"""值守编制与速率计算测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.duty import (
    MAX_DUTY_SLOTS,
    DutyMember,
    assign,
    compute_rates,
    unassign,
)
from app.models.save import DiscipleState, GameState

TEMPLATES = {
    "d_attack": {"id": "d_attack", "lean": "attack", "rarity": 3},
    "d_support": {"id": "d_support", "lean": "support", "rarity": 2},
    "d_craft": {"id": "d_craft", "lean": "craft", "rarity": 1},
}
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def make_state(*template_ids: str) -> GameState:
    """构造只含指定模板弟子的空存档。"""
    return GameState(
        disciples=[
            DiscipleState(id=f"i{i}", template_id=tid, realm=1)
            for i, tid in enumerate(template_ids)
        ]
    )


def test_empty_duty_has_zero_rates() -> None:
    """空编制时五类加成都是 0。"""
    assert set(compute_rates([]).values()) == {0.0}


def test_attack_lean_feeds_cultivation() -> None:
    """攻倾向只加修为产出，数值 = 品质系数 + 境界加成。"""
    rates = compute_rates([DutyMember(lean="attack", rarity=3, realm=1)])
    assert rates["cultivation_rate"] == pytest.approx(0.10)
    assert rates["spirit_stone_rate"] == 0.0


def test_support_lean_feeds_two_rates() -> None:
    """辅倾向同时加行动力恢复与伤势消退。"""
    rates = compute_rates([DutyMember(lean="support", rarity=2, realm=2)])
    expected = 0.06 + 2 * 0.01
    assert rates["stamina_rate"] == pytest.approx(expected)
    assert rates["injury_rate"] == pytest.approx(expected)


def test_rates_are_additive_not_multiplicative() -> None:
    """两名同倾向弟子是相加，不是乘区。"""
    rates = compute_rates(
        [
            DutyMember(lean="attack", rarity=3, realm=1),
            DutyMember(lean="attack", rarity=3, realm=1),
        ]
    )
    assert rates["cultivation_rate"] == pytest.approx(0.20)


def test_assign_adds_slot_and_event() -> None:
    """上岗后编制与事件流各增加一条。"""
    state = make_state("d_attack")
    assert assign(state, "i0", TEMPLATES, NOW) is None
    assert [slot.disciple_id for slot in state.duty_slots] == ["i0"]
    assert state.duty_events[-1].rates["cultivation_rate"] == pytest.approx(0.10)


def test_assign_rejects_duplicate() -> None:
    """同一弟子不能重复上岗。"""
    state = make_state("d_attack")
    assign(state, "i0", TEMPLATES, NOW)
    assert assign(state, "i0", TEMPLATES, NOW) == "该弟子已在值守"


def test_assign_rejects_unknown_disciple() -> None:
    """不存在的弟子不能上岗。"""
    state = make_state("d_attack")
    assert assign(state, "ghost", TEMPLATES, NOW) == "弟子不存在"


def test_assign_rejects_busy_disciple() -> None:
    """出征中的弟子不能上岗。"""
    state = make_state("d_attack")
    state.disciples[0].busy_until = NOW + timedelta(hours=1)
    assert assign(state, "i0", TEMPLATES, NOW) == "该弟子正在出征"


def test_duty_capacity_is_six() -> None:
    """第 7 人上岗被拒绝。"""
    state = make_state(*(["d_attack"] * (MAX_DUTY_SLOTS + 1)))
    for i in range(MAX_DUTY_SLOTS):
        assert assign(state, f"i{i}", TEMPLATES, NOW) is None
    assert assign(state, f"i{MAX_DUTY_SLOTS}", TEMPLATES, NOW) == "值守编制已满（6 人）"


def test_unassign_removes_slot_and_records_event() -> None:
    """下岗后编制减少，事件流继续追加而不是覆盖。"""
    state = make_state("d_attack", "d_craft")
    assign(state, "i0", TEMPLATES, NOW)
    assign(state, "i1", TEMPLATES, NOW)
    events_before = len(state.duty_events)

    assert unassign(state, "i0", TEMPLATES, NOW) is None
    assert [slot.disciple_id for slot in state.duty_slots] == ["i1"]
    assert len(state.duty_events) == events_before + 1
    assert state.duty_events[-1].rates["cultivation_rate"] == 0.0


def test_unassign_rejects_absent_disciple() -> None:
    """不在编制里的弟子不能下岗。"""
    state = make_state("d_attack")
    assert unassign(state, "i0", TEMPLATES, NOW) == "该弟子不在值守"
