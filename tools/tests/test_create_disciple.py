"""tools/create_disciple.py 的实际风险检查。

覆盖数值平衡、确定性、形态差异、风格母题、引用校验和 apply 安全。
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import create_disciple as cd  # noqa: E402

BRIEF = TOOLS / "examples" / "disciple-brief-sunwukong.json"


@pytest.fixture()
def brief() -> dict:
    return json.loads(BRIEF.read_text(encoding="utf-8"))


@pytest.fixture()
def package(brief: dict) -> dict:
    return cd.build_package(copy.deepcopy(brief))


def power(stats: dict[str, float]) -> float:
    return stats["atk"] + stats["def"] * 0.5 + stats["hp"] * 0.1


def config_tree(tmp_path: Path) -> tuple[Path, Path]:
    """最小配置树：只保留角色创建需要的集合，避免依赖主城资产。"""
    config = tmp_path / "config"
    for name in ("disciples", "skills", "bonds", "style"):
        shutil.copytree(cd.CONFIG_DIR / name, config / name)
    assets = tmp_path / "assets"
    assets.mkdir()
    # 校验器只检查 PNG 是否存在；测试用空文件代替已有 16 人的立绘。
    for data in cd.load_collection(config / "disciples").values():
        path = assets / f"{data['asset_id']}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    return config, assets


def test_demo_character_is_balanced_and_style_consistent(package: dict) -> None:
    disciple = package["disciple"]
    stats = disciple["base_stats"]
    assert disciple["id"] == "sunwukong"
    assert disciple["name"] == "孙悟空"
    assert disciple["rarity"] == 3 and disciple["lean"] == "attack"
    assert abs(power(stats) - package["brief"]["power_target"]) <= 0.6
    for stat, (low, high) in cd.STAT_RANGES.items():
        assert low <= stats[stat] <= high, stat
    motifs = package["brief"]["motifs"]
    for key in ("active", "passive"):
        assert any(motif in package[key]["description"] for motif in motifs), key
    assert any(motif in package["brief"]["visual"] for motif in motifs)
    assert package["active"]["effects"] == []
    assert package["active"]["actions"][0]["kind"] == "damage"
    assert package["passive"]["bonuses"] == {"damage": .12}
    assert package["bond"]["modifiers"][0]["skill"] == "sunwukong-art"
    assert package["bond"]["members"] == ["sunwukong", "nezha"]
    assert package["art"]["status"] == "pending"


def test_generation_is_deterministic(brief: dict) -> None:
    first = cd.build_package(copy.deepcopy(brief))
    second = cd.build_package(copy.deepcopy(brief))
    assert first == second


def test_profiles_shift_shape_without_breaking_balance(brief: dict) -> None:
    burst = cd.build_package(copy.deepcopy(brief))
    bruiser_brief = copy.deepcopy(brief)
    bruiser_brief["profile"] = "bruiser"
    bruiser = cd.build_package(bruiser_brief)
    burst_stats = burst["disciple"]["base_stats"]
    bruiser_stats = bruiser["disciple"]["base_stats"]
    assert burst_stats["atk"] > bruiser_stats["atk"]
    assert burst_stats["hp"] < bruiser_stats["hp"]
    assert abs(power(burst_stats) - burst["brief"]["power_target"]) <= 0.6
    assert abs(power(bruiser_stats) - bruiser["brief"]["power_target"]) <= 0.6


def test_rejects_unmotivated_skill_text(brief: dict) -> None:
    brief["passive"]["description"] = "身形愈发轻快，闪转腾挪之间避开敌人锋芒。"
    with pytest.raises(cd.BriefError, match="母题"):
        cd.build_package(brief)


def test_rejects_generic_skill_name(brief: dict) -> None:
    brief["active"]["name"] = "攻击"
    with pytest.raises(cd.BriefError, match="通用词"):
        cd.build_package(brief)


def test_rejects_unknown_bond_member(brief: dict) -> None:
    brief["bond"]["members"] = ["sunwukong", "nobody"]
    with pytest.raises(cd.BriefError, match="不存在"):
        cd.build_package(brief)


def test_rejects_existing_disciple_id(brief: dict) -> None:
    brief["id"] = "libai"
    with pytest.raises(cd.BriefError, match="已存在"):
        cd.build_package(brief)


def test_rejects_power_override_far_from_benchmark(brief: dict) -> None:
    brief["power_target"] = 60
    with pytest.raises(cd.BriefError, match="power_target"):
        cd.build_package(brief)


def test_generated_package_passes_config_validation(package: dict) -> None:
    assert cd.validate_package(package) == []


def test_write_draft_creates_reviewable_files(package: dict, tmp_path: Path) -> None:
    draft = cd.write_draft(package, tmp_path)
    for name in ("brief.json", "disciple.json", "skill-active.json", "skill-passive.json", "bond.json", "art-prompt.json", "balance-report.md"):
        assert (draft / name).is_file(), name
    report = (draft / "balance-report.md").read_text(encoding="utf-8")
    assert "基础参考分" in report
    assert "孙悟空" in report
    assert "金箍棒" in report


def test_apply_requires_art_or_explicit_pending(package: dict, tmp_path: Path) -> None:
    config, assets = config_tree(tmp_path)
    with pytest.raises(cd.BriefError, match="立绘"):
        cd.apply_package(package, config_dir=config, assets_dir=assets)
    assert not (config / "disciples" / "sunwukong.json").exists()

    written = cd.apply_package(package, config_dir=config, assets_dir=assets, allow_pending=True)
    assert {path.name for path in written} == {
        "sunwukong.json", "sunwukong-art.json", "sunwukong-passive.json", "qitian.json",
        "nezha.json",
    }
    nezha = json.loads((config / "disciples" / "nezha.json").read_text(encoding="utf-8"))
    assert "qitian" in nezha["bonds"]
    pending = json.loads((config / "assets_pending.json").read_text(encoding="utf-8"))
    assert "trial-v04/sunwukong" in pending
    assert cd.validate(config, assets) == []


def test_apply_with_ready_asset_clears_pending(package: dict, tmp_path: Path) -> None:
    config, assets = config_tree(tmp_path)
    asset = assets / "trial-v04" / "sunwukong.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"test")
    cd.apply_package(package, config_dir=config, assets_dir=assets)
    assert (config / "disciples" / "sunwukong.json").is_file()
    nezha = json.loads((config / "disciples" / "nezha.json").read_text(encoding="utf-8"))
    assert "qitian" in nezha["bonds"]
    pending_path = config / "assets_pending.json"
    assert not pending_path.exists() or "trial-v04/sunwukong" not in json.loads(
        pending_path.read_text(encoding="utf-8")
    )
    assert cd.validate(config, assets) == []


@pytest.mark.parametrize("asset_id", ["C:/outside/portrait", "trial-v04/../portrait", "//host/portrait", "trial-v04/portrait?x=1"])
def test_rejects_unsafe_asset_paths(brief: dict, asset_id: str) -> None:
    brief["asset_id"] = asset_id
    with pytest.raises(cd.BriefError, match="asset_id"):
        cd.build_package(brief)


def test_rejects_duplicate_bond_members(brief: dict) -> None:
    brief["bond"]["members"] = ["sunwukong", "sunwukong"]
    with pytest.raises(cd.BriefError, match="重复"):
        cd.build_package(brief)


def test_force_preserves_existing_character_bonds(brief: dict) -> None:
    brief["id"] = "libai"
    brief["bond"] = None
    existing = cd.load_collection(cd.CONFIG_DIR / "disciples")["libai"]
    assert existing["bonds"]
    package = cd.build_package(brief, force=True)
    assert package["disciple"]["bonds"] == existing["bonds"]


@pytest.mark.parametrize("part,changes", [
    ("active", {"stat": "atk", "scope": "battle", "value": .2}),
    ("passive", {"bonuses": {"pill_rate": .1}}),
    ("active", {"actions": [{"kind": "damage", "target": "enemy_first", "count": 7}]}),
    ("active", {"actions": [{"kind": "buff", "target": "all_allies", "stat": "hp", "value": .1}]}),
    ("active", {"actions": [{"kind": "damage", "target": "enemy_first", "coefficient": float("inf")}]}),
])
def test_rejects_nonexecutable_skill_configuration(brief: dict, part: str, changes: dict) -> None:
    brief[part].update(changes)
    with pytest.raises(cd.BriefError):
        cd.build_package(brief)


def test_rejects_unimplemented_duty_bond_output(brief: dict) -> None:
    brief["bond"].pop("modifiers")
    brief["bond"]["effects"] = [{"stat": "pill_rate", "scope": "duty", "mode": "add_pct", "value": .1}]
    with pytest.raises(cd.BriefError, match="产出类属性"):
        cd.build_package(brief)


def test_rejects_modifier_for_nonmember_skill(brief: dict) -> None:
    brief["bond"]["modifiers"][0]["skill"] = "guanyu-art"
    with pytest.raises(cd.BriefError, match="羁绊成员"):
        cd.build_package(brief)


def test_defaults_create_executable_actions_and_combat_passive(brief: dict) -> None:
    brief["active"] = {key: brief["active"][key] for key in ("name", "description")}
    brief["passive"] = {key: brief["passive"][key] for key in ("name", "description")}
    package = cd.build_package(brief)
    assert package["active"]["actions"] == cd.ACTIVE_DEFAULTS["attack"]
    assert package["passive"]["bonuses"] == {"damage": .12}
    assert cd.validate_package(package) == []


@pytest.mark.parametrize("part,changes", [
    ("active", {"cooldown": 1}),
    ("active", {"actions": [{"kind": "damage", "target": "enemy_first", "coefficient": 4}]}),
    ("active", {"actions": [{"kind": "damage", "target": "all_enemies", "count": 6, "coefficient": 2}]}),
    ("passive", {"bonuses": {"damage": .5}}),
])
def test_generator_rejects_executable_but_excessive_skill_budget(brief, part, changes):
    brief[part].update(changes)
    with pytest.raises(cd.BriefError):
        cd.build_package(brief)


@pytest.mark.parametrize("stat", ["atk", "def", "hp", "spd"])
def test_generator_rejects_conditional_attribute_passives(brief, stat):
    brief["passive"].update(condition="shielded", bonuses={stat: .15})
    with pytest.raises(cd.BriefError, match="条件被动只支持"):
        cd.build_package(brief)
    brief["passive"]["condition"] = "always"
    assert cd.validate_package(cd.build_package(brief)) == []


def test_regenerating_draft_without_bond_removes_stale_bond(brief: dict, tmp_path: Path) -> None:
    draft = cd.write_draft(cd.build_package(brief), tmp_path)
    assert (draft / "bond.json").exists()
    brief["bond"] = None
    cd.write_draft(cd.build_package(brief), tmp_path)
    assert not (draft / "bond.json").exists()


def test_report_describes_duty_as_percentage(package: dict) -> None:
    assert "10.0%" in package["report"]
    assert "0.100/时" not in package["report"]
