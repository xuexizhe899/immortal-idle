"""招募测试：声望解锁、升境界与重复保护。"""

from __future__ import annotations

import pytest

from app.domain.recruit import recruit
from app.models.save import GameState, Resources

TEMPLATES = {
    "d1": {
        "id": "d1",
        "unlock_cost": {"reputation": 100},
        "base_stats": {"hp": 10, "atk": 3, "def": 2, "spd": 4},
    }
}


def make_state(reputation: float) -> GameState:
    """构造带指定声望的空存档。"""
    return GameState(resources=Resources(reputation=reputation))


def test_recruit_unlocks_disciple() -> None:
    """声望足够时解锁弟子并加入阵容。"""
    state = make_state(150)

    assert recruit(state, "d1", TEMPLATES) is None
    assert "d1" in state.unlocks
    assert len(state.disciples) == 1
    assert state.resources.reputation == pytest.approx(50)


def test_recruit_rejects_insufficient_reputation() -> None:
    """声望不足时不扣钱也不加人。"""
    state = make_state(10)

    assert "声望不足" in (recruit(state, "d1", TEMPLATES) or "")
    assert state.disciples == []
    assert "d1" not in state.unlocks


def test_recruit_rejects_unknown_template() -> None:
    """模板不存在时直接报错。"""
    state = make_state(999)
    assert recruit(state, "ghost", TEMPLATES) == "弟子模板不存在"


def test_recruit_owned_raises_realm() -> None:
    """已拥有时再招募，改成提升境界并收半价。"""
    state = make_state(300)

    recruit(state, "d1", TEMPLATES)
    assert recruit(state, "d1", TEMPLATES) is None

    assert state.disciples[0].realm == 2
    assert state.resources.reputation == pytest.approx(150)


def test_recruit_owned_does_not_duplicate() -> None:
    """重复招募不会产生第二个同名弟子。"""
    state = make_state(300)

    recruit(state, "d1", TEMPLATES)
    recruit(state, "d1", TEMPLATES)

    assert len(state.disciples) == 1


def test_recruit_owned_needs_half_cost() -> None:
    """升境界也要付半价，声望不够照样拒绝。"""
    state = make_state(120)

    recruit(state, "d1", TEMPLATES)
    assert "声望不足" in (recruit(state, "d1", TEMPLATES) or "")
    assert state.disciples[0].realm == 1
