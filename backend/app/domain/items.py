"""丹药使用：炼制先入行囊，服用时指定弟子并立即生效。

属性丹与生产丹只写个人加成，不写宗门 `bonuses`；
疗伤与破境复用伤势、突破规则，失败时不扣丹药。
"""

from __future__ import annotations

from app.domain.duty import RATE_KEYS, DutyMember, compute_rates
from app.domain.facilities import GRADE_MULTIPLIERS
from app.domain.craft import craft
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
    recipe_id, separator, suffix = item_id.partition(":g")
    grade = int(suffix) if separator and suffix in {"2", "3"} else 1
    if separator and suffix not in {"2", "3"}:
        return "丹药品级无效"
    recipe = recipes.get(recipe_id)
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
    grades: list[int] = []
    delta = GRADE_MULTIPLIERS[grade]
    if special and grade != 1:
        return "功能丹药不支持提升品级"
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
        # 旧档次数代表已生效的一品名额；只记录品级，不重发旧药效。
        grades = list(disciple.pill_grades.get(recipe_id, [1] * disciple.pill_uses.get(recipe_id, 0)))
        if max_uses is not None and len(grades) >= max_uses:
            lowest = min(grades)
            if grade <= lowest:
                return f"{recipe['name']}每名弟子最多服用 {max_uses} 次；需更高品级才能替换"
            delta -= GRADE_MULTIPLIERS[lowest]
            grades[grades.index(lowest)] = grade
        else:
            grades.append(grade)
        if all(effect["stat"] in RATE_KEYS for effect in effects):
            template = templates.get(disciple.template_id)
            if template is None:
                return "弟子模板未配置"
            # 生产丹只培养个人值守贡献；倾向不匹配时不扣库存或服用次数。
            # 未上岗的弟子也可提前服用，比较其上岗后的真实收益。
            bonuses = dict(disciple.bonuses)
            for effect in effects:
                bonuses[effect["stat"]] = bonuses.get(effect["stat"], 0.0) + effect["value"] * delta
            before = compute_rates([DutyMember(
                template["lean"], template["rarity"], disciple.realm, disciple.bonuses,
            )])
            after = compute_rates([DutyMember(
                template["lean"], template["rarity"], disciple.realm, bonuses,
            )])
            if not any(after[key] > before[key] for key in RATE_KEYS):
                return "该丹药无法提升该弟子的值守产出"

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
            disciple.bonuses[stat] = disciple.bonuses.get(stat, 0.0) + effect["value"] * delta

    if special:
        disciple.pill_uses[recipe_id] = disciple.pill_uses.get(recipe_id, 0) + 1
    else:
        disciple.pill_grades[recipe_id] = grades
        disciple.pill_uses[recipe_id] = len(grades)
    return None


def heal_party_preview(state: GameState, party: list[str], recipes: dict[str, dict]) -> dict:
    """按伤势和队列确定可治疗对象，只计算本次实际缺额。"""
    result = {"injured_count": 0, "healed": [], "crafted": 0, "stock_used": 0, "costs": {}, "reason": ""}
    if state.active_run is not None:
        result["reason"] = "请先完成当前出征再疗伤"
        return result
    if not 1 <= len(party) <= 6 or len(set(party)) != len(party):
        result["reason"] = "请选择一至六名不重复的弟子"
        return result
    by_id = {disciple.id: disciple for disciple in state.disciples}
    if any(member not in by_id for member in party):
        result["reason"] = "队伍中有不存在的弟子"
        return result
    if any(is_on_run(state, by_id[member]) for member in party):
        result["reason"] = "出征中的弟子暂不可疗伤"
        return result
    injured = sorted(
        (by_id[member] for member in party if by_id[member].injury_stacks > 0),
        key=lambda disciple: -disciple.injury_stacks,
    )
    result["injured_count"] = len(injured)
    if not injured:
        result["reason"] = "队伍无人受伤"
        return result
    inputs = recipes["liao_shang_dan"]["inputs"]
    stock = min(len(injured), pill_stock(state, "liao_shang_dan"))
    craftable = min((state.inventory.get(key, 0) // count for key, count in inputs.items()), default=0)
    crafted = min(len(injured) - stock, craftable)
    result.update(
        healed=[disciple.id for disciple in injured[:stock + crafted]],
        crafted=crafted, stock_used=stock,
        costs={key: count * crafted for key, count in inputs.items()} if crafted else {},
    )
    if not result["healed"]:
        result["reason"] = "疗伤丹与补炼材料不足"
    return result


def heal_party(state: GameState, party: list[str], recipes: dict[str, dict]) -> dict:
    """库存先用，缺几颗补几颗，再统一治疗；一次命令内完成全部消耗。"""
    result = heal_party_preview(state, party, recipes)
    if result["reason"]:
        return result
    if result["crafted"]:
        error = craft(state, "liao_shang_dan", recipes, result["crafted"])
        if error:
            return {**result, "reason": error}
    by_id = {disciple.id: disciple for disciple in state.disciples}
    for member in result["healed"]:
        consume_pill(state, "liao_shang_dan")
        disciple = by_id[member]
        heal(disciple)
        disciple.pill_uses["liao_shang_dan"] = disciple.pill_uses.get("liao_shang_dan", 0) + 1
    return result
