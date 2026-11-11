"""炼制：消耗材料，产出永久加成或特殊效果。

首版不做装备栏：炼成即生效，加成记在 `state.bonuses`，出征时叠加到战力。
"""

from __future__ import annotations

from app.domain.injuries import heal
from app.models.save import GameState

SPECIALS = {"heal", "realm"}


def craft(
    state: GameState, recipe_id: str, target: str | None, recipes: dict[str, dict]
) -> str | None:
    """炼制一件配方；成功返回 None，失败返回原因。"""
    if state.active_run is not None:
        return "请先完成当前出征再炼制"
    recipe = recipes.get(recipe_id)
    if recipe is None:
        return "配方不存在"

    for material_id, count in recipe["inputs"].items():
        if state.inventory.get(material_id, 0) < count:
            return f"材料不足：{material_id}"

    special = recipe.get("special")
    disciple = None
    if special in SPECIALS:
        if target is None:
            return "该配方需要指定弟子"
        disciple = next((d for d in state.disciples if d.id == target), None)
        if disciple is None:
            return "弟子不存在"

    for material_id, count in recipe["inputs"].items():
        state.inventory[material_id] -= count
        if state.inventory[material_id] <= 0:
            del state.inventory[material_id]

    if special == "heal":
        heal(disciple)  # type: ignore[arg-type]
    elif special == "realm":
        disciple.realm += 1  # type: ignore[union-attr]
    else:
        for effect in recipe.get("effects", []):
            if effect["scope"] != "permanent" or effect["mode"] != "add_pct":
                continue
            state.bonuses[effect["stat"]] = (
                state.bonuses.get(effect["stat"], 0.0) + effect["value"]
            )

    return None
