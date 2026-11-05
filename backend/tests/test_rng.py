"""确定性随机与词条抽取测试。"""

from __future__ import annotations

import pytest

from app.domain.affix import draw, weights_for
from app.domain.rng import Pcg32

AFFIXES = [
    {"id": "fire_1", "group": "fire", "weight": 1.0},
    {"id": "fire_2", "group": "fire", "weight": 1.0},
    {"id": "water_1", "group": "water", "weight": 1.0},
    {"id": "earth_1", "group": "earth", "weight": 1.0},
]


def test_same_seed_gives_same_sequence() -> None:
    """相同种子产生完全相同的序列。"""
    left, right = Pcg32(42), Pcg32(42)
    assert [left.next_u32() for _ in range(5)] == [right.next_u32() for _ in range(5)]


def test_different_seed_differs() -> None:
    """不同种子产生不同序列。"""
    left, right = Pcg32(1), Pcg32(2)
    assert [left.next_u32() for _ in range(5)] != [right.next_u32() for _ in range(5)]


def test_advance_to_resumes_sequence() -> None:
    """按游标恢复后，后续序列与原序列一致。"""
    reference = Pcg32(7)
    expected = [reference.next_u32() for _ in range(6)]

    rng = Pcg32(7)
    head = [rng.next_u32() for _ in range(3)]
    resumed = Pcg32(7)
    resumed.advance_to(rng.cursor)

    assert head + [resumed.next_u32() for _ in range(3)] == expected


def test_randint_stays_in_range() -> None:
    """randint 的结果始终落在闭区间内。"""
    rng = Pcg32(11)
    assert {rng.randint(3, 5) for _ in range(50)} <= {3, 4, 5}


def test_cursor_counts_warmup_and_draws() -> None:
    """游标累计包含预热与显式调用，可据此恢复。"""
    rng = Pcg32(1)
    start = rng.cursor
    rng.next_u32()
    rng.randint(1, 10)
    assert rng.cursor == start + 2


def test_weights_grow_with_chosen_group() -> None:
    """同组每已选一条，权重按 1 + 0.5 × 条数 增长。"""
    weights = dict(weights_for(AFFIXES, {"fire": 2}))
    assert weights["fire_1"] == pytest.approx(2.0)
    assert weights["water_1"] == pytest.approx(1.0)


def test_boosted_group_outweighs_others() -> None:
    """高权重组的总权重明显超过其它组。"""
    weights = dict(weights_for(AFFIXES, {"fire": 20}))
    assert weights["fire_1"] > weights["water_1"] * 10


def test_draw_returns_unique_ids() -> None:
    """三选一不重复。"""
    picked = draw(Pcg32(3), AFFIXES, {})
    assert len(picked) == 3
    assert len(set(picked)) == 3


def test_draw_is_reproducible() -> None:
    """同种子同已选组，抽取结果一致。"""
    assert draw(Pcg32(9), AFFIXES, {"fire": 1}) == draw(Pcg32(9), AFFIXES, {"fire": 1})


def test_draw_respects_candidate_count() -> None:
    """候选不足三个时按实际数量返回。"""
    assert len(draw(Pcg32(4), AFFIXES[:2], {})) == 2
