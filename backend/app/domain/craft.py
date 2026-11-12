"""炼制：消耗材料，丹药入行囊，法器提供宗门永久加成。

丹药不再在炼制时直接服用；指定弟子服用由 `domain/items.py` 单独处理。
普通器方每档只能打造一次，避免永久加成无限叠加；不与弟子专属武器混用。
"""

from __future__ import annotations

from app.models.save import GameState


def craft(
    state: GameState, recipe_id: str, recipes: dict[str, dict],
) -> str | None:
    """炼制一件配方；成功返回 None，失败返回原因且不扣材料。"""
    if state.active_run is not None:
        return "请先完成当前出征再炼制"
    recipe = recipes.get(recipe_id)
    if recipe is None:
        return "配方不存在"
    if recipe["kind"] == "artifact" and recipe_id in state.crafted_recipes:
        return "该法器已打造，无法重复炼制"

    for material_id, count in recipe["inputs"].items():
        if state.inventory.get(material_id, 0) < count:
            return f"材料不足：{material_id}"

    for material_id, count in recipe["inputs"].items():
        state.inventory[material_id] -= count
        if state.inventory[material_id] <= 0:
            del state.inventory[material_id]

    if recipe["kind"] == "pill":
        state.inventory[recipe_id] = state.inventory.get(recipe_id, 0) + 1
        return None

    for effect in recipe.get("effects", []):
        if effect["scope"] != "permanent" or effect["mode"] != "add_pct":
            continue
        state.bonuses[effect["stat"]] = (
            state.bonuses.get(effect["stat"], 0.0) + effect["value"]
        )
    state.crafted_recipes.append(recipe_id)

    return None
