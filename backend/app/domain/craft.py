"""炼制与器具升级：预览和执行使用同一份费用与品级规则。"""

from __future__ import annotations

from app.domain.facilities import GRADE_MULTIPLIERS
from app.models.api import RecipeView
from app.models.save import GameState


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
    if state.active_run is not None:
        reason = "请先完成当前出征再炼制"
    elif artifact and current >= 3:
        reason = "该法器已达最高等级"
    elif grade > max_grade:
        reason = "请先升级炼器炉" if artifact else "请先升级炼丹房"
    elif maximum < 1:
        reason = "材料不足"
    key = pill_inventory_key(recipe_id, grade) if not artifact else recipe_id
    return RecipeView(
        id=recipe_id, name=recipe["name"], kind=recipe["kind"], grade=grade,
        max_grade=max_grade, current_level=current, inputs=inputs,
        effects=[{**effect, "value": effect["value"] * GRADE_MULTIPLIERS[grade]} for effect in recipe.get("effects", [])],
        inventory_key=key, stock=state.inventory.get(key, 0),
        max_quantity=0 if reason else min(maximum, 1) if artifact else maximum, reason=reason,
    )


def craft(
    state: GameState, recipe_id: str, recipes: dict[str, dict],
    quantity: int = 1, grade: int = 1,
) -> str | None:
    """一次扣除全部材料；器具升阶只增加该器具前后品级的差额。"""
    if state.active_run is not None:
        return "请先完成当前出征再炼制"
    recipe = recipes.get(recipe_id)
    if recipe is None:
        return "配方不存在"
    if type(quantity) is not int or quantity < 1:
        return "炼制数量必须是正整数"
    if type(grade) is not int or grade not in GRADE_MULTIPLIERS:
        return "炼制品级必须为一至三品"
    artifact = recipe["kind"] == "artifact"
    current = state.recipe_levels.get(recipe_id, 1 if recipe_id in state.crafted_recipes else 0)
    if artifact:
        if grade <= current:
            return "该法器已打造，无法重复炼制"
        if quantity != 1 or grade != current + 1:
            return "法器每次只能提升一级"
    elif recipe.get("special") and grade != 1:
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
    if not artifact:
        state.inventory[view.inventory_key] = state.inventory.get(view.inventory_key, 0) + quantity
        return None

    # 旧档已有器具按一级处理，其已计入的宗门加成不能再次发放。
    delta = GRADE_MULTIPLIERS[grade] - (GRADE_MULTIPLIERS[current] if current else 0)
    for effect in recipe.get("effects", []):
        if effect["scope"] == "permanent" and effect["mode"] == "add_pct":
            stat = effect["stat"]
            state.bonuses[stat] = state.bonuses.get(stat, 0.0) + effect["value"] * delta
    state.recipe_levels[recipe_id] = grade
    if recipe_id not in state.crafted_recipes:
        state.crafted_recipes.append(recipe_id)
    return None
