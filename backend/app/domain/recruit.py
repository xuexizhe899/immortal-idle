"""弟子招募：声望解锁；已拥有弟子的境界提升由培养命令处理。

不做付费抽卡；重复获得不给免费碎片，避免无限刷。
"""

from __future__ import annotations

from app.models.save import DiscipleState, GameState


def recruit(
    state: GameState, template_id: str, templates: dict[str, dict]
) -> str | None:
    """只处理首次招募；成功返回 None，失败返回原因。"""
    template = templates.get(template_id)
    if template is None:
        return "弟子模板不存在"
    if template_id in state.unlocks:
        return "已拥有该弟子，请在培养界面突破境界"

    cost = template.get("unlock_cost", {}).get("reputation", 0.0)
    if state.resources.reputation < cost:
        return f"声望不足（需要 {cost:g}）"

    state.resources.reputation -= cost
    state.unlocks.append(template_id)
    state.disciples.append(
        DiscipleState(
            id=template_id,
            template_id=template_id,
            stats=dict(template["base_stats"]),
        )
    )
    return None
