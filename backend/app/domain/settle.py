"""惰性挂机结算。

没有常驻 tick：读取存档时按 last_settled_at 与 now 的时间差补算。
速率会随值守变更而变，所以区间要按 duty_events 切段逐段求和。
代价：一段时间的产出 = 基础速率 × (1 + 加成) × 小时数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.save import GameState

# 基础产出（每小时），加成走加区：基础 × (1 + 加成)
BASE_CULTIVATION_PER_HOUR = 1.0
BASE_SPIRIT_STONE_PER_HOUR = 0.5
BASE_STAMINA_PER_HOUR = 0.5
BASE_MATERIALS_PER_HOUR = {
    "ling_cao": 0.5, "yun_mu": 0.25, "han_tie": 0.25,
    "jiao_gu": 0.15, "xuan_jing": 0.1, "jiu_ye": 0.1,
    "ling_mu": 0.5, "qing_shi": 0.5, "chi_tong": 0.5, "yao_shou_pi": 0.5,
    "gong_fa_qi_pei": 0.0, "hu_chi_qi_pei": 0.0, "po_jing_ling_cai": 0.0,
}

# 离线最多补算 12 小时，超出部分丢弃
IDLE_CAP_HOURS = 12.0

# 日志最多保留条数，避免存档无限膨胀
LOG_LIMIT = 50


@dataclass
class SettleReport:
    """一次补算的结果摘要。"""

    elapsed_hours: float = 0.0
    dropped_hours: float = 0.0
    cultivation: float = 0.0
    spirit_stone: float = 0.0
    stamina: float = 0.0
    materials: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def material_production(rates: dict[str, float]) -> dict[str, float]:
    """基础材料享受值守加成，专长与外宗驻守按实际时产叠加。"""
    return {
        material: base * (1 + rates.get("material_rate", 0.0))
        + rates.get(f"material_{material}_flat", 0.0)
        for material, base in BASE_MATERIALS_PER_HOUR.items()
    }


def rate_segments(
    state: GameState, start: datetime, end: datetime
) -> list[tuple[datetime, datetime, dict[str, float]]]:
    """把 [start, end] 按值守事件切段，返回 (段起点, 段终点, 该段速率)。"""
    events = sorted(state.duty_events, key=lambda event: event.at)

    current: dict[str, float] = {}
    for event in events:
        if event.at <= start:
            current = event.rates
        else:
            break

    segments: list[tuple[datetime, datetime, dict[str, float]]] = []
    cursor = start
    for event in events:
        if not start < event.at < end:
            continue
        segments.append((cursor, event.at, current))
        cursor = event.at
        current = event.rates
    segments.append((cursor, end, current))
    return segments


def settle(state: GameState, last_settled_at: datetime, now: datetime) -> SettleReport:
    """按经过时间补算挂机产出，原地更新 state 并返回报告。"""
    report = SettleReport()

    raw_hours = (now - last_settled_at).total_seconds() / 3600
    if raw_hours < 0:
        report.warnings.append(f"时钟回拨 {raw_hours:.2f}h，按 0 处理")

    if raw_hours <= 0:
        window_start = now
        report.elapsed_hours = 0.0
        report.dropped_hours = 0.0
    else:
        window_start = max(last_settled_at, now - timedelta(hours=IDLE_CAP_HOURS))
        report.elapsed_hours = (now - window_start).total_seconds() / 3600
        report.dropped_hours = raw_hours - report.elapsed_hours

    material_gains = dict.fromkeys(BASE_MATERIALS_PER_HOUR, 0.0)
    extra_recovery_hours = 0.0
    for seg_start, seg_end, duty_rates in rate_segments(state, window_start, now):
        rates = {
            key: duty_rates.get(key, 0.0) + state.bonuses.get(key, 0.0)
            for key in set(duty_rates) | set(state.bonuses)
        }
        hours = (seg_end - seg_start).total_seconds() / 3600
        if hours <= 0:
            continue
        report.cultivation += (
            BASE_CULTIVATION_PER_HOUR * (1 + rates.get("cultivation_rate", 0.0)) * hours
        )
        report.spirit_stone += (
            BASE_SPIRIT_STONE_PER_HOUR * (1 + rates.get("spirit_stone_rate", 0.0)) * hours
        )
        report.stamina += (
            BASE_STAMINA_PER_HOUR * (1 + rates.get("stamina_rate", 0.0)) * hours
        )
        for material, per_hour in material_production(rates).items():
            material_gains[material] += per_hour * hours
        extra_recovery_hours += max(0.0, rates.get("injury_rate", 0.0)) * hours

    state.resources.cultivation += report.cultivation
    state.resources.spirit_stone += report.spirit_stone
    state.resources.stamina += report.stamina

    for material, gain in material_gains.items():
        total = gain + state.material_remainders.get(material, 0.0)
        count = int(total + 1e-9)
        state.material_remainders[material] = max(0.0, total - count)
        if count:
            state.inventory[material] = state.inventory.get(material, 0) + count
            report.materials[material] = count

    for disciple in state.disciples:
        if disciple.injured_until is not None:
            disciple.injured_until -= timedelta(hours=extra_recovery_hours)
        if disciple.injured_until is not None and disciple.injured_until <= now:
            disciple.injury_stacks = 0
            disciple.injured_until = None

    for warning in report.warnings:
        state.logs.append(warning)
    if len(state.logs) > LOG_LIMIT:
        del state.logs[: len(state.logs) - LOG_LIMIT]

    return report
