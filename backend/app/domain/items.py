"""丹药使用：炼制先入行囊，服用时指定弟子并立即生效。

属性丹与生产丹只写个人加成，不写宗门 `bonuses`；
疗伤与破境复用伤势、突破规则，失败时不扣丹药。
"""

from __future__ import annotations

from app.domain.injuries import heal
from app.domain.progression import breakthrough, can_breakthrough, is_on_run
from app.models.save import DiscipleState, GameState

# 旧档遗留的疗伤物品入口，正式丹方 ID 是 liao_shang_dan。
PILL_ALIASES = {"healing_pill": "liao_shang_dan"}
SPECIALS = {"heal", "realm"}


def canonical_pill_id(item_id: str) -> str:
    """把遗留别名折算成正式丹方 ID。"""
    return PILL_ALIASES.get(item_id, item_id)


def stock_ids(item_id: str) -> tuple[str, ...]:
    """读取库存键；疗伤丹优先消耗旧的 healing_pill。"""
    canonical = canonical_pill_id(item_id)
    if canonical == "liao_shang_dan":
        return ("healing_pill", canonical)
    return (canonical,)


def pill_stock(state: GameState, item_id: str) -> int:
    """同名丹药与遗留物品的可用总数。"""
    return sum(state.inventory.get(key, 0) for key in stock_ids(item_id))


def consume_pill(state: GameState, item_id: str) -> None:
    """按旧物品优先的顺序扣除 1 个丹药。"""
    for key in stock_ids(item_id):
        count = state.inventory.get(key, 0)
        if count <= 0:
            continue
        if count == 1:
            del state.inventory[key]
        else:
            state.inventory[key] = count - 1
        return


def use_pill(
    state: GameState, disciple_id: str, item_id: str,
    recipes: dict[str, dict], templates: dict[str, dict],
) -> str | None:
    """让一名弟子服用丹药；成功返回 None，失败返回原因且不扣物品。"""
    item_id = canonical_pill_id(item_id)
    recipe = recipes.get(item_id)
    if recipe is None or recipe.get("kind") != "pill":
        return "该物品不是可服用的丹药"
    if state.active_run is not None:
        return "请先完成当前出征再服用丹药"

    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return "弟子不存在"
    if is_on_run(state, disciple):
        return "出征中的弟子暂不可服用丹药"

    special = recipe.get("special")
    effects: list[dict] = []
    if special is not None and special not in SPECIALS:
        return "该丹药效果未实现"
    if special == "heal":
        if disciple.injury_stacks <= 0:
            return "该弟子没有伤势"
    elif special == "realm":
        template = templates.get(disciple.template_id)
        if template is None:
            return "弟子模板未配置"
        _, error = can_breakthrough(
            state, disciple, template, pay_reputation=False,
        )
        if error:
            return error
    else:
        effects = [
            effect for effect in recipe.get("effects", [])
            if effect.get("scope") == "permanent" and effect.get("mode") == "add_pct"
        ]
        if not effects:
            return "该丹药没有可用效果"
        max_uses = recipe.get("max_uses")
        if max_uses is not None and disciple.pill_uses.get(item_id, 0) >= max_uses:
            return f"{recipe['name']}每名弟子最多服用 {max_uses} 次"

    if pill_stock(state, item_id) < 1:
        return f"{recipe['name']}不足"

    consume_pill(state, item_id)
    if special == "heal":
        heal(disciple)
    elif special == "realm":
        _, error = breakthrough(  # type: ignore[arg-type]
            state, disciple.id, templates, pay_reputation=False,
        )
        if error:
            return error
    else:
        for effect in effects:
            stat = effect["stat"]
            disciple.bonuses[stat] = disciple.bonuses.get(stat, 0.0) + effect["value"]

    disciple.pill_uses[item_id] = disciple.pill_uses.get(item_id, 0) + 1
    return None
