"""Tool wrapper exposing direct Discovery Engine recipe search to the agents
— see discovery_engine_client.py docstring for why this replaces
VertexAiSearchTool. Product search now goes through kurly_client.py instead
(real-time Kurly API, not a data store) — see that module.
"""
import os

from recifit_agent.discovery_engine_client import search_data_store

RECIPES_DATA_STORE_ID = os.getenv("RECIPES_DATA_STORE_ID", "recipes_1786339291426")


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
