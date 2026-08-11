"""Tool wrapper exposing the deterministic ingredient text parser to the agent."""
from recifit_agent.ingredient_parser import parse_ingredients_block, parse_servings


def parse_recipe_ingredients(raw_ingredients_text: str) -> dict:
    """레시피의 재료 원문 텍스트를 재료별로 나눠 이름·수량·단위로 구조화한다.

    예: "[재료] 소고기 100 g | 불린미역 50 g | 다진마늘 1 작은술" 같은 원문을
    받아서 각 재료를 {name, amount, unit, raw} 형태로 쪼갠다. 정규식 기반의
    코드 로직으로 처리하며, 숫자를 추측하거나 새로 만들지 않는다.

    Args:
        raw_ingredients_text: 레시피 문서의 ingredients 필드 원문.

    Returns:
        {"ingredients": [{name, amount, unit, raw}, ...]} 형태의 dict.
    """
    return {"ingredients": parse_ingredients_block(raw_ingredients_text)}


def parse_recipe_servings(raw_servings_text: str) -> dict:
    """레시피의 인분 표기(예: "6인분이상", "1인분")를 숫자로 변환한다.

    Args:
        raw_servings_text: 레시피 문서의 servings 필드 원문.

    Returns:
        {"servings": float} 형태의 dict.
    """
    return {"servings": parse_servings(raw_servings_text)}
