"""羁绊测试：触发条件、加成叠加与战力提升。"""

from __future__ import annotations

import pytest

from app.config_loader import load_bonds, load_disciples
from app.domain.run_engine import bond_bonus, party_power
from app.models.save import DiscipleState

BONDS = {
    "pair": {
        "id": "pair",
        "members": ["a", "b"],
        "requires": 2,
        "effects": [{"stat": "atk", "mode": "add_pct", "value": 0.1, "scope": "run"}],
    },
    "trio": {
        "id": "trio",
        "members": ["a", "b", "c"],
        "requires": 3,
        "effects": [{"stat": "def", "mode": "add_pct", "value": 0.2, "scope": "run"}],
    },
    "duty_only": {
        "id": "duty_only",
        "members": ["a"],
        "requires": 1,
        "effects": [
            {"stat": "cultivation_rate", "mode": "add_pct", "value": 0.5, "scope": "duty"}
        ],
    },
}


def test_bond_triggers_when_required_members_present() -> None:
    """满员时触发加成。"""
    assert bond_bonus(["a", "b"], BONDS) == {"atk": 0.1}


def test_bond_skips_when_members_missing() -> None:
    """缺员时不触发。"""
    assert bond_bonus(["a"], BONDS) == {}


def test_trio_bond_needs_all_three() -> None:
    """三人羁绊只到两人时不触发。"""
    assert "def" not in bond_bonus(["a", "b"], BONDS)


def test_bonus_accumulates_across_bonds() -> None:
    """同时触发多个羁绊时加成相加。"""
    bonus = bond_bonus(["a", "b", "c"], BONDS)

    assert bonus["atk"] == pytest.approx(0.1)
    assert bonus["def"] == pytest.approx(0.2)


def test_duty_scope_excluded_from_run_bonus() -> None:
    """duty 作用域的加成不计入出征战力。"""
    assert "cultivation_rate" not in bond_bonus(["a"], BONDS)


def test_bonus_raises_party_power() -> None:
    """同样的队伍，带羁绊加成时战力更高。"""
    templates = {
        "t": {"id": "t", "base_stats": {"hp": 100, "atk": 20, "def": 10, "spd": 10}}
    }
    party = [DiscipleState(id="x", template_id="t")]

    plain = party_power(party, templates)
    boosted = party_power(party, templates, {"atk": 0.5})

    assert boosted > plain


def test_repo_has_at_least_three_run_bonds() -> None:
    """出征羁绊现在是成员技能强化，值守羁绊仍独立。"""
    bonds = load_bonds()
    run_bonds = [
        bond
        for bond in bonds.values()
        if bond.get("modifiers")
    ]

    assert len(run_bonds) >= 3


def test_repo_run_bonds_modify_member_skills() -> None:
    """真实羁绊绑定成员技能，不再同时叠加旧的全队百分比。"""
    bonds = load_bonds()
    templates = load_disciples()

    for bond in bonds.values():
        if not bond.get("modifiers"):
            continue
        member_skills = {templates[member]["skill"] for member in bond["members"]}
        assert all(modifier["skill"] in member_skills for modifier in bond["modifiers"])
        assert not any(effect["scope"] == "run" for effect in bond["effects"])
