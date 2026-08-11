"""Tool wrapper that lets the agent report the conditions it parsed out of
the user's request (household size, budget, excluded/fridge items, meal
count) as a structured value instead of only prose.

The web frontend reads this the same way it reads get_recipe — straight
from the tool's functionResponse in the /run_sse event stream — so it can
(a) sync the condition-bar UI (household stepper etc.) to whatever was
actually used, even when the user only said it in a chat sentence rather
than clicking the stepper, and (b) use condition_summary, not the raw
message text, when displaying a saved favorite's conditions.
"""


def record_conditions(
    household_size: float,
    budget: float | None,
    excluded_items: list[str],
    fridge_items: list[str],
    meal_count: float,
    condition_summary: str,
) -> dict:
    """1단계에서 정리한 사용자 조건을 구조화된 형태로 기록한다.

    계산은 하지 않고 받은 값을 그대로 돌려주기만 한다 — 반드시 1번에서
    이미 정리한 값을 그대로 넣는다(새로 추측해서 만들지 않는다). 화면이
    이 결과를 읽어서 인원수 등 조건 표시를 실제 반영된 값으로 맞추고,
    즐겨찾기 저장 시 조건 요약으로 사용한다.

    Args:
        household_size: 1번에서 정한 가구 인원수.
        budget: 1번에서 정한 예산. 없으면 None.
        excluded_items: 1번에서 정한 알레르기/제외 재료 목록.
        fridge_items: 1번에서 정한 보유 재료(냉장고에 이미 있는 것) 목록.
        meal_count: 1번에서 정한 몇 끼/며칠 분량인지.
        condition_summary: 위 조건을 사람이 읽기 좋게 한국어 한 줄로 새로
            쓴 요약(예: "1인 가구 · 예산 제한 없음 · 간식용으로 여러 끼
            오래 보관해 먹을 예정"). 사용자가 보낸 문장을 그대로 복사하지
            말고 핵심만 간결하게 정리한다.

    Returns:
        입력값을 그대로 담은 dict.
    """
    return {
        "household_size": household_size,
        "budget": budget,
        "excluded_items": excluded_items,
        "fridge_items": fridge_items,
        "meal_count": meal_count,
        "condition_summary": condition_summary,
    }
