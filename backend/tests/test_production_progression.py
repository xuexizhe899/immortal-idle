"""资源分段小数、辅助恢复及永久成长的真实效果。"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config_loader import load_bonds, load_disciples
from app.domain.duty import assign
from app.domain.progression import upgrade
from app.domain.run_engine import party_power
from app.domain.settle import settle
from app.models.save import DiscipleState, DutyEvent, GameState, Resources

T0 = datetime(2026, 11, 11, tzinfo=timezone.utc)


def test_material_fractions_make_split_settlement_equivalent():
    whole = GameState()
    split = GameState()
    settle(whole, T0, T0 + timedelta(hours=10))
    for hour in range(10):
        settle(split, T0 + timedelta(hours=hour), T0 + timedelta(hours=hour + 1))
    assert split.inventory == whole.inventory
    assert split.material_remainders == pytest.approx(whole.material_remainders)


def test_support_recovery_and_permanent_production_actually_apply():
    state = GameState(
        disciples=[DiscipleState(
            id="d", template_id="guanyu", injury_stacks=1,
            injured_until=T0 + timedelta(hours=4),
        )],
        bonuses={"cultivation_rate": .2, "material_rate": 1},
        duty_events=[DutyEvent(at=T0, rates={"injury_rate": 1})],
    )
    settle(state, T0, T0 + timedelta(hours=2))
    assert state.disciples[0].injury_stacks == 0
    assert state.resources.cultivation == pytest.approx(2.4)
    assert state.inventory["ling_cao"] == 2


def test_upgrade_spends_both_resources_and_level_and_realm_raise_power():
    disciple = DiscipleState(id="g", template_id="guanyu")
    state = GameState(
        disciples=[disciple], resources=Resources(cultivation=20, spirit_stone=10),
    )
    base = party_power([disciple], load_disciples())
    costs, error = upgrade(state, "g")
    assert error is None
    assert costs == {"cultivation": 20, "spirit_stone": 10}
    assert state.resources.cultivation == state.resources.spirit_stone == 0
    assert party_power([disciple], load_disciples()) == pytest.approx(base * 1.1)
    disciple.realm += 1
    assert party_power([disciple], load_disciples()) == pytest.approx(base * 1.15)


def test_poet_bond_in_duty_is_recorded_and_produces_cultivation():
    state = GameState(disciples=[
        DiscipleState(id="l", template_id="libai"),
        DiscipleState(id="d", template_id="dufu"),
    ])
    templates, bonds = load_disciples(), load_bonds()
    assign(state, "l", templates, T0, bonds)
    before = state.duty_events[-1].rates["cultivation_rate"]
    assign(state, "d", templates, T0, bonds)
    after = state.duty_events[-1].rates["cultivation_rate"]
    expected_personal = (
        .10 if templates["dufu"]["lean"] == "attack" else 0
    )
    assert after - before == pytest.approx(.10 + expected_personal)
    settle(state, T0, T0 + timedelta(hours=1))
    assert state.resources.cultivation == pytest.approx(1 + after)
