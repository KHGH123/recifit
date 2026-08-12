"""Builds the full grocery cart for a recipe in a single deterministic pass.

Before this module existed, the root agent looped per ingredient calling
scale_ingredient_amount -> product_search_agent (a whole separate LLM
sub-agent) -> pick_cheapest_product. That's roughly five Gemini round trips
per ingredient (the root agent's own tool-calling turns plus the sub-agent's
own reasoning + structured-output turns) — for a recipe with 8-10
ingredients, minutes of pure LLM latency for work that is otherwise fast and
deterministic (the Kurly search itself takes well under a second). This
collapses the whole per-ingredient loop into one tool call: the model calls
it once with the parsed ingredient list, and scaling, searching Kurly,
picking the cheapest option, and summing the total all happen here in plain
Python.
"""
from recifit_agent.cart_tools import (
    is_relevant_product,
    pick_cheapest_product,
    scale_ingredient_amount,
    summarize_cart,
    to_base_unit,
)
from recifit_agent.ingredient_price_cache import record_price_observations
from recifit_agent.kurly_client import search_products


def _cache_price_observations(name: str, candidates: list[dict]) -> None:
    # 나중에 [A]단계 예상가(estimate_recipe_price)가 실시간 조회 없이 쓸 수
    # 있도록, 실제로 고른 상품 하나뿐 아니라 검색된 후보 전체의 단위가격을
    # 캐시에 쌓는다 — 후보가 많을수록 평균이 실제 시세에 가까워진다.
    # 가격 캐시는 부가 기능이라 Firestore 오류가 나도 장보기 흐름 자체는
    # 계속돼야 하므로 실패를 조용히 무시한다.
    #
    # 관련 없는 상품(마켓컬리 검색이 잘못 매칭해준 것, 예: "대파"인데
    # "팽이버섯"이 나옴)까지 그대로 캐시에 넣으면 [A]단계 참고가가 엉뚱한
    # 가격으로 오염되므로, pick_cheapest_product와 같은 기준으로 먼저 거른다.
    relevant_candidates = [c for c in candidates if is_relevant_product(name, c.get("name", ""))]
    buckets: dict[str, list[float]] = {}
    sample_names: dict[str, str] = {}
    for candidate in relevant_candidates:
        price = candidate.get("price")
        if price is None:
            continue
        base = to_base_unit(candidate.get("pkg_amount"), candidate.get("pkg_unit"))
        if base:
            base_amount, unit = base
            if not base_amount:
                continue
            unit_price = price / base_amount
        else:
            unit, unit_price = "개", price
        buckets.setdefault(unit, []).append(unit_price)
        sample_names.setdefault(unit, candidate.get("name"))

    for unit, prices in buckets.items():
        try:
            record_price_observations(name, unit, prices, sample_names.get(unit))
        except Exception:
            pass


def build_shopping_list(
    ingredients: list[dict],
    recipe_servings: float,
    household_size: float,
    exclude_terms: list[str],
    budget: float | None = None,
    meal_count: float = 1.0,
) -> dict:
    """레시피 재료 전체에 대해 인원수/끼니 수에 맞는 상품을 한 번에 찾고 총액까지 계산한다.

    parse_recipe_ingredients가 돌려준 재료 목록을 그대로 넣으면, 재료마다
    필요량 환산(scale_ingredient_amount) -> 마켓컬리 실시간 검색 ->
    필요량을 채우는 최저가 상품 선택(pick_cheapest_product)을 이 함수
    안에서 전부 순서대로 처리하고, 총액·예산 이내 여부(summarize_cart)까지
    한 번에 계산해서 돌려준다. 재료마다 따로 도구를 호출할 필요가 없다.
    알레르기/제외 재료(exclude_terms)와 이름이 겹치는 상품도 여기서
    걸러진다.

    Args:
        ingredients: parse_recipe_ingredients가 돌려준 {name, amount, unit, raw} 목록
            (이미 알레르기/제외 재료로 걸러낸, "조건을 충족한 재료"만 넣는다).
        recipe_servings: 레시피가 기준으로 하는 인분 수.
        household_size: 사용자의 실제 가구 인원수.
        exclude_terms: 상품명에서 걸러낼 알레르기/제외 재료 이름 목록.
        budget: 사용자 예산. 없으면 None.
        meal_count: 몇 끼/며칠 분량을 만들지 (기본 1끼).

    Returns:
        {"selections": [...], "total_price", "budget", "within_budget"} 형태의
        dict. selections의 각 항목은 {ingredient, scaled_amount, unit,
        selected, quantity, subtotal, skipped_reason}이며, selected가 있으면
        그 상품의 url을 그대로 사용자에게 보여줘도 된다.
    """
    selections = []
    for ingredient in ingredients:
        name = ingredient.get("name") or ""
        unit = ingredient.get("unit")
        scale = scale_ingredient_amount(ingredient.get("amount"), recipe_servings, household_size, meal_count)

        candidates = search_products(name)["results"] if name else []
        if candidates:
            _cache_price_observations(name, candidates)
        picked = pick_cheapest_product(scale["scaled_amount"], unit, candidates, exclude_terms, ingredient_name=name)

        selections.append(
            {
                "ingredient": name,
                "scaled_amount": scale["scaled_amount"],
                "unit": unit,
                "selected": picked["selected"],
                "quantity": picked["quantity"],
                "subtotal": picked["subtotal"],
                "skipped_reason": picked["skipped_reason"],
            }
        )

    summary = summarize_cart(selections, budget)
    return {"selections": selections, **summary}
