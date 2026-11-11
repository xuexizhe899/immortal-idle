"""弟子招募：声望解锁，已拥有则转为升境界。

不做付费抽卡；重复获得不给免费碎片，避免无限刷。
"""

from __future__ import annotations

from app.models.save import DiscipleState, GameState
from app.domain.progression import is_on_run

# 已拥有时再招募，消耗原价的这个比例来提升境界
REALM_UP_RATIO = 0.5


def recruit(
    state: GameState, template_id: str, templates: dict[str, dict]
) -> str | None:
    """招募或升境界；成功返回 None，失败返回原因。"""
    template = templates.get(template_id)
    if template is None:
        return "弟子模板不存在"

    base_cost = template.get("unlock_cost", {}).get("reputation", 0.0)

    if template_id in state.unlocks:
        owned = next((d for d in state.disciples if d.template_id == template_id), None)
        if owned is not None and is_on_run(state, owned):
            return "出征中的弟子暂不可提升境界"
        cost = base_cost * REALM_UP_RATIO
        if state.resources.reputation < cost:
            return f"声望不足（需要 {cost:g}）"
        state.resources.reputation -= cost
        for disciple in state.disciples:
            if disciple.template_id == template_id:
                disciple.realm += 1
                break
        return None

    if state.resources.reputation < base_cost:
        return f"声望不足（需要 {base_cost:g}）"

    state.resources.reputation -= base_cost
    state.unlocks.append(template_id)
    state.disciples.append(
        DiscipleState(
            id=template_id,
            template_id=template_id,
            stats=dict(template["base_stats"]),
        )
    )
    return None
