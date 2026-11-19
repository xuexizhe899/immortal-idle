"""丹药炼制；旧普通器方保留查询，装备由掉落和个人强化取得。"""

from __future__ import annotations

from app.domain.facilities import GRADE_MULTIPLIERS
from app.models.api import RecipeView
from app.models.save import GameState

ARTIFACT_REASON = "普通装备通过副本与首领掉落，请前往炼器阁强化或熔炼"


def recipe_inputs(recipe: dict, grade: int) -> dict[str, int]:
    return {key: count * grade for key, count in recipe["inputs"].items()}


def pill_inventory_key(recipe_id: str, grade: int) -> str:
    return recipe_id if grade == 1 else f"{recipe_id}:g{grade}"


def recipe_view(state: GameState, recipe: dict, grade: int = 1) -> RecipeView:
    recipe_id = recipe["id"]
    artifact = recipe["kind"] == "artifact"
    current = state.recipe_levels.get(recipe_id, 1 if recipe_id in state.crafted_recipes else 0)
    max_grade = state.facility_levels.get("forge" if artifact else "alchemy", 1)
    if recipe.get("special"):
        max_grade = 1
        grade = 1
    if artifact:
        grade = min(current + 1, 3)
    inputs = recipe_inputs(recipe, grade)
    maximum = min((state.inventory.get(key, 0) // count for key, count in inputs.items()), default=0)
    reason = ""
    if artifact:
        reason = ARTIFACT_REASON
    elif state.active_run is not None:
        reason = "请先完成当前出征再炼制"
    elif grade > max_grade:
        reason = "请先升级炼丹房"
    elif maximum < 1:
        reason = "材料不足"
    key = pill_inventory_key(recipe_id, grade) if not artifact else recipe_id
    return RecipeView(
        id=recipe_id, name=recipe["name"], kind=recipe["kind"], grade=grade,
        max_grade=max_grade, current_level=current, inputs=inputs,
        effects=[{**effect, "value": effect["value"] * GRADE_MULTIPLIERS[grade]} for effect in recipe.get("effects", [])],
        inventory_key=key, stock=state.inventory.get(key, 0),
        max_quantity=0 if reason else maximum, reason=reason,
    )


def craft(
    state: GameState, recipe_id: str, recipes: dict[str, dict],
    quantity: int = 1, grade: int = 1,
) -> str | None:
    """一次扣除所选品级丹药的全部材料，普通器具不再制造宗门被动。"""
    if state.active_run is not None:
        return "请先完成当前出征再炼制"
    recipe = recipes.get(recipe_id)
    if recipe is None:
        return "配方不存在"
    if type(quantity) is not int or quantity < 1:
        return "炼制数量必须是正整数"
    if type(grade) is not int or grade not in GRADE_MULTIPLIERS:
        return "炼制品级必须为一至三品"
    if recipe["kind"] == "artifact":
        return ARTIFACT_REASON
    if recipe.get("special") and grade != 1:
        return "功能丹药不支持提升品级"
    view = recipe_view(state, recipe, grade)
    if view.reason:
        return view.reason
    if quantity > view.max_quantity:
        return "材料不足，无法炼制指定数量"

    for material_id, count in view.inputs.items():
        remaining = state.inventory[material_id] - count * quantity
        if remaining:
            state.inventory[material_id] = remaining
        else:
            del state.inventory[material_id]
    state.inventory[view.inventory_key] = state.inventory.get(view.inventory_key, 0) + quantity
    return None
