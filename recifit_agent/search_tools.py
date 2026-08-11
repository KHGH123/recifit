"""Tool wrappers exposing direct Discovery Engine search to the agents —
see discovery_engine_client.py docstring for why this replaces
VertexAiSearchTool for recipe/product lookups.
"""
import os

from recifit_agent.discovery_engine_client import search_data_store

RECIPES_DATA_STORE_ID = os.getenv("RECIPES_DATA_STORE_ID", "recipes_1786339291426")
PRODUCTS_DATA_STORE_ID = os.getenv("PRODUCTS_DATA_STORE_ID", "recifit-products")


def search_recipes(query: str, max_results: int = 5) -> dict:
    """레시피 데이터스토어에서 음식명으로 레시피를 검색한다.

    결과의 recipe_id 필드가 그 레시피의 진짜 고유 ID다 — 새로 만들거나
    번호를 다시 매기지 말고, 이후 도구 호출(get_recipe 등)에 그대로
    복사해서 써라.

    Args:
        query: 검색할 음식명/재료명 (예: "김치찌개").
        max_results: 최대 결과 개수.

    Returns:
        {"results": [{recipe_id, title, name, description, ingredients,
        servings, difficulty, cooking_time}, ...]} 형태의 dict.
    """
    results = search_data_store(RECIPES_DATA_STORE_ID, query, page_size=max_results)
    for r in results:
        r["recipe_id"] = r.pop("id")
    return {"results": results}


def search_products(ingredient_name: str, max_results: int = 5) -> dict:
    """상품 데이터스토어에서 재료명으로 구매 가능한 상품을 검색한다.

    결과의 id/product_id, price, pkg_amount, pkg_unit, vendor, url은 전부
    실제 값이니 그대로 사용해라 — 가격이나 용량을 스스로 만들어내지 않는다.

    Args:
        ingredient_name: 검색할 재료명 (예: "돼지고기").
        max_results: 최대 결과 개수.

    Returns:
        {"results": [{id, product_id, name, price, pkg_amount, pkg_unit,
        vendor, url}, ...]} 형태의 dict.
    """
    return {"results": search_data_store(PRODUCTS_DATA_STORE_ID, ingredient_name, page_size=max_results)}
