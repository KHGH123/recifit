import json

import requests
from bs4 import BeautifulSoup


def get_recipe(recipe_id: str) -> dict:
    """레시피 ID로 만개의레시피 원본 페이지에서 조리순서·재료·이미지를 가져온다.

    사용자가 후보 목록에서 레시피를 하나 선택한 뒤, 상세 조리순서를
    보여줄 때만 호출한다 (목록을 보여줄 때는 호출하지 않는다).

    Args:
        recipe_id: 레시피 문서 ID (예: "1000240").

    Returns:
        title, description, image, ingredients, instructions를 담은 dict.
        페이지에서 레시피 정보를 못 찾으면 {"error": ...}를 담은 dict.
    """
    url = f"https://www.10000recipe.com/recipe/{recipe_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": f"페이지를 불러오지 못했습니다: {exc}"}

    soup = BeautifulSoup(response.text, "html.parser")

    # JSON-LD 추출
    recipe_data = None
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            data = json.loads(script.string)

            if isinstance(data, dict):
                if data.get("@type") == "Recipe":
                    recipe_data = data
                    break

            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Recipe":
                        recipe_data = item
                        break

        except Exception:
            continue

    if recipe_data is None:
        return {"error": "레시피 정보를 찾을 수 없습니다."}

    title = recipe_data.get("name")
    description = recipe_data.get("description")
    image = recipe_data.get("image")
    ingredients = recipe_data.get("recipeIngredient", [])

    instructions = []
    for step in recipe_data.get("recipeInstructions", []):
        if isinstance(step, dict):
            text = step.get("text")
            if text:
                instructions.append(text)
        elif isinstance(step, str):
            instructions.append(step)

    return {
        "id": recipe_id,
        "url": url,
        "title": title,
        "description": description,
        "image": image,
        "ingredients": ingredients,
        "instructions": instructions,
    }
