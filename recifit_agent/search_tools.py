"""Tool wrapper exposing direct Discovery Engine recipe search to the agents
— see discovery_engine_client.py docstring for why this replaces
VertexAiSearchTool. Product search now goes through kurly_client.py instead
(real-time Kurly API, not a data store) — see that module.
"""
import os

from recifit_agent.discovery_engine_client import search_data_store

RECIPES_DATA_STORE_ID = os.getenv("RECIPES_DATA_STORE_ID", "recipes_1786339291426")


def _contains_any(text: str, terms: list[str]) -> bool:
    normalized = (text or "").lower()
    return any(term.lower() in normalized for term in terms if term)


def search_recipes(query: str, max_results: int = 5, exclude_terms: list[str] | None = None) -> dict:
    """레시피 데이터스토어에서 음식명으로 레시피를 검색한다.

    결과의 recipe_id 필드가 그 레시피의 진짜 고유 ID다 — 새로 만들거나
    번호를 다시 매기지 말고, 이후 도구 호출(get_recipe 등)에 그대로
    복사해서 써라.

    exclude_terms를 넘기면 재료 원문(ingredients)에 그 단어가 포함된
    레시피는 결과에서 아예 빠진다 — 알레르기/제외 재료뿐 아니라 "매운
    거 싫어" 같은 취향에서 뽑아낸 회피 키워드(예: "청양고추", "고추장")도
    같이 넣을 수 있다. 사용자에게 후보를 보여주기 전에 여기서 코드로
    걸러내서, 조건에 안 맞는 레시피가 애초에 후보 목록에 뜨지 않게 한다.

    Args:
        query: 검색할 음식명/재료명 (예: "김치찌개").
        max_results: 최대 결과 개수.
        exclude_terms: 재료 원문에서 걸러낼 단어 목록(알레르기/제외 재료 +
            취향 기반 회피 키워드). 없으면 필터링하지 않는다.

    Returns:
        {"results": [{recipe_id, title, name, description, ingredients,
        servings, difficulty, cooking_time}, ...]} 형태의 dict.
    """
    # 필터링으로 결과가 줄어들 걸 감안해 넉넉히 가져온 뒤 앞에서부터 자른다.
    fetch_size = max_results * 3 if exclude_terms else max_results
    results = search_data_store(RECIPES_DATA_STORE_ID, query, page_size=fetch_size)
    for r in results:
        r["recipe_id"] = r.pop("id")
    if exclude_terms:
        results = [r for r in results if not _contains_any(r.get("ingredients", ""), exclude_terms)]
    return {"results": results[:max_results]}
