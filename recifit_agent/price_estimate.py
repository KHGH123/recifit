"""[A]-stage rough price estimate, grounded in real cached Kurly prices
instead of a pure LLM guess.

Doing a live Kurly search per ingredient per candidate here would
reintroduce the exact per-ingredient latency shopping_list.py was built to
eliminate — for several candidates at once that's minutes again. Instead
this reads ingredient_price_cache.py, which build_shopping_list keeps
filled from real [B-2] runs (see that module's docstring): fast Firestore
lookups, no live HTTP calls, so it's cheap enough to call once per
candidate. Ingredients never priced before (or only priced with a stale
cache entry) come back in unknown_ingredients for the model to guess, same
as before this existed.
"""
from recifit_agent import ingredient_price_cache
from recifit_agent.cart_tools import scale_ingredient_amount, to_base_unit
from recifit_agent.ingredient_parser import parse_ingredients_block, parse_servings


def estimate_recipe_price(
    raw_ingredients_text: str,
    raw_servings_text: str,
    household_size: float,
    meal_count: float = 1.0,
) -> dict:
    """[A] 단계 후보 레시피의 예상 총액을, 캐시된 실제 마켓컬리 가격으로 빠르게 추정한다.

    실시간 검색은 하지 않는다 — build_shopping_list가 실사용 중 쌓아온
    재료별 실제 단위가격 캐시(recifit_ingredient_price_cache)를 조회해서,
    인원수·끼니 수에 맞게 환산한 금액을 계산해준다. 오래된(기본 7일 초과)
    캐시 항목은 이미 없는 것으로 취급되니 따로 신경 쓰지 않아도 된다.

    Args:
        raw_ingredients_text: 후보 레시피의 재료 원문(ingredients 필드).
        raw_servings_text: 후보 레시피의 인분 원문(servings 필드).
        household_size: 사용자의 실제 가구 인원수.
        meal_count: 몇 끼/며칠 분량인지.

    Returns:
        {"known_total": 캐시로 계산된 소계(원, 정수), "unknown_ingredients":
        캐시에 없어 계산 못한 재료 이름 목록, "priced_count": 캐시로 계산한
        재료 수, "total_count": 전체 재료 수} 형태의 dict. 최종 예상가는
        known_total에 unknown_ingredients 몫을 네 일반 지식으로 대략 더한
        값이다.
    """
    ingredients = parse_ingredients_block(raw_ingredients_text)
    recipe_servings = parse_servings(raw_servings_text)

    lookup_keys: list[tuple[str, str]] = []
    priced_amounts: dict[tuple[str, str], float] = {}
    for ingredient in ingredients:
        name = ingredient.get("name")
        if not name:
            continue
        scale = scale_ingredient_amount(ingredient.get("amount"), recipe_servings, household_size, meal_count)
        base = to_base_unit(scale["scaled_amount"], ingredient.get("unit"))
        key = (name, base[1]) if base else (name, "개")
        qty = base[0] if base else 1.0
        lookup_keys.append(key)
        priced_amounts[key] = qty

    cached = ingredient_price_cache.get_unit_prices(lookup_keys)

    known_total = 0.0
    priced_count = 0
    unknown_ingredients: list[str] = []
    for key in lookup_keys:
        entry = cached.get(key)
        if not entry:
            unknown_ingredients.append(key[0])
            continue
        known_total += entry.get("avg_unit_price", 0.0) * priced_amounts[key]
        priced_count += 1

    return {
        "known_total": round(known_total),
        "unknown_ingredients": unknown_ingredients,
        "priced_count": priced_count,
        "total_count": len(ingredients),
    }
