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
from recifit_agent.cart_tools import pick_cheapest_product, scale_ingredient_amount, summarize_cart
from recifit_agent.kurly_client import search_products


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
        picked = pick_cheapest_product(scale["scaled_amount"], unit, candidates, exclude_terms)

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
