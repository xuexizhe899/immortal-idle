"""自然消伤、配置修改与重启均不能改写一局的固定输入。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.config_loader import load_affixes, load_bonds, load_disciples, load_modes, load_enemies, load_skills
from app.domain.run_engine import choose, pick_affix, run_status, start_run
from app.domain.settle import settle
from app.models.save import DiscipleState, GameState, Resources

T0 = datetime(2026, 11, 11, tzinfo=timezone.utc)


def injured_state():
    return GameState(resources=Resources(stamina=3), bonuses={"atk": .15}, disciples=[
        DiscipleState(id=key, template_id=key, level=2, realm=2, injury_stacks=1, injured_until=T0 + timedelta(hours=4))
        for key in ("guanyu", "zhangfei", "zhaoyun")
    ])


def test_natural_healing_and_permanent_changes_do_not_change_run_replay():
    immediate = injured_state()
    assert start_run(immediate, [d.id for d in immediate.disciples], load_disciples(), load_modes()["tower"], T0, seed=61, bonds=load_bonds()) is None
    delayed = GameState.model_validate_json(immediate.model_dump_json())
    settle(delayed, T0, T0 + timedelta(hours=4))
    assert all(d.injury_stacks == 0 for d in delayed.disciples)
    delayed.disciples[0].level = 100
    delayed.bonuses["atk"] = 100
    frozen = immediate.active_run.party_snapshot
    while run_status(immediate.active_run) not in {"cleared", "defeated"}:
        if immediate.active_run.affix_pending:
            option = immediate.active_run.affix_options[0]
            assert pick_affix(immediate, option) is None
            assert pick_affix(delayed, option) is None
        else:
            assert choose(immediate, 0) is None
            assert choose(delayed, 0) is None
            assert immediate.active_run.last_battle == delayed.active_run.last_battle
    assert immediate.active_run == delayed.active_run
    with pytest.raises(ValidationError):
        frozen.combatants[0].attack = 999


def test_configuration_definitions_are_deep_copied_and_survive_serialization():
    mode, skills, enemies = deepcopy(load_modes()["tower"]), deepcopy(load_skills()), deepcopy(load_enemies())
    affixes, bonds = deepcopy(load_affixes()), deepcopy(load_bonds())
    state = injured_state()
    start_run(state, [d.id for d in state.disciples], load_disciples(), mode, T0, seed=1, bonds=bonds, skills=skills, enemies=enemies, affix_pool=affixes)
    expected = GameState.model_validate_json(state.model_dump_json())
    mode["enemy_growth"] = 99
    mode["rewards"]["battle"]["cultivation"] = 99999
    enemies["stone_guard"]["base_stats"]["hp"] = 99999
    skills["guanyu-art"]["actions"][0]["coefficient"] = .01
    next(item for item in affixes if item["id"] == "tie_bi")["effects"][0]["value"] = 99
    next(item for item in affixes if item["id"] == "po_jun")["bonuses"]["damage"] = 99
    bonds["wuhu"]["modifiers"][0]["extra_actions"][0]["value"] = 99
    assert state.active_run.party_snapshot == expected.active_run.party_snapshot
    choose(expected, 0)
    choose(state, 0)
    assert state.active_run == expected.active_run
