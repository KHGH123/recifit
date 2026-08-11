from recifit_agent.ingredient_parser import parse_ingredients_block, parse_ingredient_line, parse_servings


def test_parse_simple_line_with_unit():
    result = parse_ingredient_line("돼지고기 300g")
    assert result["name"] == "돼지고기"
    assert result["amount"] == 300
    assert result["unit"] == "g"


def test_parse_fraction_amount():
    result = parse_ingredient_line("양파 1/2개")
    assert result["amount"] == 0.5
    assert result["unit"] == "개"


def test_parse_uppercase_liter_unit():
    result = parse_ingredient_line("물 1.5 L")
    assert result["name"] == "물"
    assert result["amount"] == 1.5
    assert result["unit"] == "L"


def test_parse_block_does_not_merge_ingredients_across_section_header():
    block = "소금 약간 [생굴 세척] 갈색설탕 2 스푼"
    ingredients = parse_ingredients_block(block)
    by_name = {i["name"]: i for i in ingredients}
    assert "소금" in by_name
    assert by_name["갈색설탕"]["amount"] == 2


def test_parse_real_dataset_sample():
    block = "[재료] 소고기 100 g | 불린미역 50 g | 다진마늘 1 작은술 | 참기름 조금 | 물 300 ml"
    ingredients = parse_ingredients_block(block)
    assert len(ingredients) == 5
    assert ingredients[0]["name"] == "소고기"
    assert ingredients[0]["amount"] == 100


def test_parse_servings_from_korean_text():
    assert parse_servings("1인분") == 1.0
    assert parse_servings("6인분이상") == 6.0
    assert parse_servings(None) == 1.0
