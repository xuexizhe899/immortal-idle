"""伤势：叠加、消退与战斗修正。

规则：最多 3 层，每层攻击 -10%，只在出征战斗内计算；
`injured_until` 到期自动清空，疗伤丹可以立即清除。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.save import DiscipleState

MAX_INJURY_STACKS = 3
ATTACK_PENALTY_PER_STACK = 0.1
HOURS_PER_STACK = 4.0


def attack_multiplier(stacks: int) -> float:
    """伤势对攻击的乘区修正，最多扣到 0.7。"""
    capped = min(max(stacks, 0), MAX_INJURY_STACKS)
    return 1.0 - ATTACK_PENALTY_PER_STACK * capped


def apply_injury(disciple: DiscipleState, now: datetime) -> None:
    """失败后叠加一层伤势，并按当前层数顺延消退时间。"""
    disciple.injury_stacks = min(MAX_INJURY_STACKS, disciple.injury_stacks + 1)
    disciple.injured_until = now + timedelta(
        hours=HOURS_PER_STACK * disciple.injury_stacks
    )


def heal(disciple: DiscipleState) -> None:
    """清除全部伤势（疗伤丹效果）。"""
    disciple.injury_stacks = 0
    disciple.injured_until = None
