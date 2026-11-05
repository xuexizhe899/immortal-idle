"""词条抽取：按协同组加权后不放回抽三条。

规则：已选某组的词条越多，该组后续权重越高（每条 +50%），
让一局之内更容易凑出成套 build，而不是三个互不相干的废选项。
"""

from __future__ import annotations

from app.domain.rng import Pcg32, UINT32_SPAN

GROUP_BONUS = 0.5


def weights_for(
    candidates: list[dict], chosen_groups: dict[str, int], bonus: float = GROUP_BONUS
) -> list[tuple[str, float]]:
    """计算候选词条的抽取权重：同组每已选一条，权重乘以 (1 + bonus)。"""
    return [
        (
            affix["id"],
            affix.get("weight", 1.0) * (1 + bonus * chosen_groups.get(affix["group"], 0)),
        )
        for affix in candidates
    ]


def draw(
    rng: Pcg32, candidates: list[dict], chosen_groups: dict[str, int], count: int = 3
) -> list[str]:
    """按权重不放回抽取 count 条词条 id。"""
    pool = weights_for(candidates, chosen_groups)
    picked: list[str] = []

    for _ in range(min(count, len(pool))):
        total = sum(weight for _, weight in pool)
        roll = rng.next_u32() / UINT32_SPAN * total
        index = len(pool) - 1
        acc = 0.0
        for i, (_, weight) in enumerate(pool):
            acc += weight
            if roll < acc:
                index = i
                break
        picked.append(pool.pop(index)[0])

    return picked
