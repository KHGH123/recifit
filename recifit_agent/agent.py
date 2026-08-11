import os

from google.adk import Agent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from recifit_agent.cart_tools import pick_cheapest_product, scale_ingredient_amount, summarize_cart
from recifit_agent.parsing_tools import parse_recipe_ingredients, parse_recipe_servings

model_name = os.getenv("MODEL", "gemini-2.5-flash")
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("DISCOVERY_ENGINE_LOCATION", "global")

RECIPES_DATA_STORE_ID = os.getenv("RECIPES_DATA_STORE_ID", "recipes_1786339291426")
PRODUCTS_DATA_STORE_ID = os.getenv("PRODUCTS_DATA_STORE_ID", "recifit-products")


def _data_store_path(data_store_id: str) -> str:
    return (
        f"projects/{project_id}/locations/{location}/collections/"
        f"default_collection/dataStores/{data_store_id}"
    )


recipe_search_tool = VertexAiSearchTool(data_store_id=_data_store_path(RECIPES_DATA_STORE_ID))
product_search_tool = VertexAiSearchTool(data_store_id=_data_store_path(PRODUCTS_DATA_STORE_ID))


# ---------------------------------------------------------------------------
# 조회 AI: 레시피 데이터스토어에서 사용자가 원하는 요리를 찾는다.
# ---------------------------------------------------------------------------
recipe_search_agent = Agent(
    name="recipe_search_agent",
    model=model_name,
    description="사용자가 원하는 요리(음식명)에 맞는 레시피를 데이터스토어에서 검색한다.",
    instruction="""
        - recipe_search_tool로 요청받은 음식명을 검색해서 레시피를 찾는다.
        - 검색 결과에서 레시피 이름, 재료(ingredients) 원문, 인분(servings) 원문을
          그대로 전달한다. 재료량이나 인분 수를 스스로 계산하거나 바꾸지 않는다.
        - 여러 결과가 있으면 가장 잘 맞는 1개를 고르고, 왜 골랐는지는 설명하지 않아도 된다.
    """,
    tools=[recipe_search_tool],
)

# ---------------------------------------------------------------------------
# 상품 검색 AI: 재료 하나에 대해 데이터스토어에서 후보 상품을 찾는다.
# ---------------------------------------------------------------------------
product_search_agent = Agent(
    name="product_search_agent",
    model=model_name,
    description="재료 하나를 입력받아 그 재료를 구매할 수 있는 상품 후보를 데이터스토어에서 검색한다.",
    instruction="""
        - product_search_tool로 요청받은 재료명을 검색해서 상품 후보들을 찾는다.
        - 검색 결과의 각 상품에 대해 product_id, name, price, pkg_amount, pkg_unit,
          vendor, url을 있는 그대로 전달한다. 가격이나 용량을 스스로 만들어내지 않는다.
        - 가구 인원수가 많다는 정보를 받으면, 대용량(pkg_amount가 큰) 상품도 포함해서
          후보로 제시한다 — 최종적으로 어떤 게 저렴한지는 계산 도구가 판단한다.
    """,
    tools=[product_search_tool],
)

# ---------------------------------------------------------------------------
# greeting/오케스트레이터 AI: 사용자 자연어 요청을 해석하고 전체 흐름을 조율한다.
# ---------------------------------------------------------------------------
root_agent = Agent(
    name="recifit_agent",
    model=model_name,
    description="예산과 조건에 맞는 레시피 원가 계산 및 장보기 추천 에이전트.",
    instruction="""
        너는 ReciFit의 장보기 도우미다. 사용자가 자연어로 "3만원 이내로 1인 20대
        남자가 먹을만한 닭 요리 추천해줘, 갑각류 알레르기가 있어서 빼줘" 같은
        요청을 하면 아래 순서로 처리한다.

        1. 사용자 요청에서 다음 조건을 추출한다: 원하는 음식/재료, 예산(원),
           가구 인원수(household_size), 알레르기/제외 재료 목록.
           빠진 조건이 있어도 되묻지 말고 바로 진행한다 — 예산이 없으면
           "예산 제한 없음"으로, 가구 인원수가 없으면 1인분(household_size=1)
           으로, 알레르기/제외 재료가 없으면 빈 목록으로 간주하고 다음 단계로
           넘어간다. 어떤 조건을 기본값으로 채웠는지는 기억해뒀다가 7번에서
           알려준다.

        2. recipe_search_agent를 호출해 조건에 맞는 레시피를 찾는다.

        3. parse_recipe_ingredients로 레시피의 재료 원문을 구조화하고,
           parse_recipe_servings로 레시피 기준 인분 수를 구한다.

        4. 재료 목록에서 알레르기·제외 재료와 겹치는 항목은 제외 목록으로 분류하고,
           나머지를 "조건을 충족한 재료" 목록으로 삼는다.

        5. 조건을 충족한 재료마다 (제외 목록은 건너뛰고) 다음을 반복한다:
           a. scale_ingredient_amount로 가구 인원수에 맞게 필요량을 환산한다
              (직접 곱셈하지 말고 반드시 이 도구를 호출한다).
           b. product_search_agent를 호출해 그 재료의 상품 후보를 받는다.
              가구 인원수가 많으면(예: 4인 이상) 대용량 상품도 함께 찾도록
              요청 문구에 인원수를 포함시킨다.
           c. pick_cheapest_product로 알레르기/제외 재료를 제외한 후보 중
              필요량을 채우는 가장 저렴한 상품을 고른다 (직접 비교하지 말고
              반드시 이 도구를 호출한다).

        6. 모든 선택 결과를 summarize_cart에 넘겨 총액과 예산 이내 여부를 구한다
           (직접 합산하지 말고 반드시 이 도구를 호출한다).

        7. 최종적으로 레시피명, 인분 환산 결과, 재료별 선택 상품과 수량,
           총 예상 비용, 예산 이내 여부를 사용자에게 자연스러운 한국어로
           정리해서 보여준다. 상품을 찾지 못한 재료는 따로 안내한다.

           마지막으로, 1번에서 사용자가 직접 말하지 않아 기본값으로 채운
           조건이 있다면, 그 조건들을 추가로 알려주면 더 정확한 추천을
           받을 수 있다는 걸 자연스럽게 안내한다. 고정된 문구를 반복하지
           말고 실제로 빠졌던 항목을 언급하되, "이것만 넣을 수 있다"는
           식으로 딱딱하게 제한하지 말고 "이런 것도 알려주면 좋다"는
           가벼운 제안 톤으로 말한다. 사용자가 세 조건을 전부 직접
           말했다면 이 안내 자체를 하지 않는다.

        숫자(가격, 수량, 총액)는 절대 네가 직접 계산하지 말고 항상 도구의
        결과값을 그대로 사용해라 — 이 프로젝트는 모델이 만들어낸 숫자를
        신뢰하지 않고 코드로 검증하는 것을 원칙으로 한다.
    """,
    tools=[
        AgentTool(agent=recipe_search_agent),
        AgentTool(agent=product_search_agent),
        parse_recipe_ingredients,
        parse_recipe_servings,
        scale_ingredient_amount,
        pick_cheapest_product,
        summarize_cart,
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.2),
)
