"""惰性结算测试：幂等、分段一致、值守换人、封顶与时钟回拨。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.settle import (
    BASE_CULTIVATION_PER_HOUR,
    BASE_SPIRIT_STONE_PER_HOUR,
    BASE_STAMINA_PER_HOUR,
    IDLE_CAP_HOURS,
    rate_segments,
    settle,
)
from app.models.save import DiscipleState, DutyEvent, GameState

T0 = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)


def hours(count: float) -> timedelta:
    """构造小时级时间差。"""
    return timedelta(hours=count)


def test_idle_hour_without_duty() -> None:
    """没有值守时按基础速率产出。"""
    state = GameState()
    settle(state, T0, T0 + hours(1))

    assert state.resources.cultivation == pytest.approx(BASE_CULTIVATION_PER_HOUR)
    assert state.resources.spirit_stone == pytest.approx(BASE_SPIRIT_STONE_PER_HOUR)
    assert state.resources.stamina == pytest.approx(BASE_STAMINA_PER_HOUR)


def test_duty_bonus_applies() -> None:
    """值守加成按 基础 × (1 + 加成) 生效。"""
    state = GameState(duty_events=[DutyEvent(at=T0, rates={"cultivation_rate": 0.5})])
    settle(state, T0, T0 + hours(2))

    assert state.resources.cultivation == pytest.approx(
        BASE_CULTIVATION_PER_HOUR * 1.5 * 2
    )


def test_split_settle_equals_single() -> None:
    """分两次补算与一次补算结果一致。"""
    whole = GameState(duty_events=[DutyEvent(at=T0, rates={"cultivation_rate": 0.5})])
    settle(whole, T0, T0 + hours(2))

    split = GameState(duty_events=[DutyEvent(at=T0, rates={"cultivation_rate": 0.5})])
    settle(split, T0, T0 + hours(1))
    settle(split, T0 + hours(1), T0 + hours(2))

    assert split.resources.cultivation == pytest.approx(whole.resources.cultivation)


def test_rate_change_midway() -> None:
    """中途换人后，前后两段按各自速率结算。"""
    state = GameState(
        duty_events=[
            DutyEvent(at=T0, rates={}),
            DutyEvent(at=T0 + hours(1), rates={"cultivation_rate": 1.0}),
        ]
    )
    settle(state, T0, T0 + hours(2))

    expected = BASE_CULTIVATION_PER_HOUR * 1 + BASE_CULTIVATION_PER_HOUR * 2
    assert state.resources.cultivation == pytest.approx(expected)


def test_clock_rollback_yields_nothing() -> None:
    """时钟回拨时不产出，并留下告警。"""
    state = GameState()
    report = settle(state, T0 + hours(1), T0)

    assert report.elapsed_hours == 0
    assert state.resources.cultivation == 0
    assert report.warnings
    assert state.logs


def test_idle_cap_drops_extra_hours() -> None:
    """超过 12 小时的部分被丢弃，只结算最近 12 小时。"""
    state = GameState()
    report = settle(state, T0, T0 + hours(20))

    assert report.elapsed_hours == pytest.approx(IDLE_CAP_HOURS)
    assert report.dropped_hours == pytest.approx(8)
    assert state.resources.cultivation == pytest.approx(
        BASE_CULTIVATION_PER_HOUR * IDLE_CAP_HOURS
    )


def test_second_settle_is_noop() -> None:
    """同一时刻重复补算不会再产出（幂等）。"""
    state = GameState()
    settle(state, T0, T0 + hours(1))
    before = state.resources.cultivation

    report = settle(state, T0 + hours(1), T0 + hours(1))

    assert report.elapsed_hours == 0
    assert state.resources.cultivation == before


def test_injury_clears_when_due() -> None:
    """伤势到期后层数与到期时间一起清空。"""
    state = GameState(
        disciples=[
            DiscipleState(
                id="d1",
                template_id="t",
                injury_stacks=2,
                injured_until=T0 + hours(1),
            )
        ]
    )
    settle(state, T0, T0 + hours(2))

    assert state.disciples[0].injury_stacks == 0
    assert state.disciples[0].injured_until is None


def test_rate_segments_split_at_event() -> None:
    """事件把区间切成两段，前段用旧速率、后段用新速率。"""
    state = GameState(duty_events=[DutyEvent(at=T0 + hours(1), rates={"a": 1.0})])
    segments = rate_segments(state, T0, T0 + hours(2))

    assert len(segments) == 2
    assert segments[0][2] == {}
    assert segments[1][2] == {"a": 1.0}
