from recifit_agent import ingredient_price_cache, price_estimate


def test_estimate_recipe_price_uses_cache_for_known_ingredients(monkeypatch):
    def fake_get_unit_prices(pairs, max_age_days=7.0):
        cache = {
            ("돼지고기", "g"): {"avg_unit_price": 20.0},  # 원/g
            ("두부", "개"): {"avg_unit_price": 1500.0},  # 원/개(포장 단위)
        }
        return {key: cache[key] for key in pairs if key in cache}

    monkeypatch.setattr(ingredient_price_cache, "get_unit_prices", fake_get_unit_prices)

    result = price_estimate.estimate_recipe_price(
        raw_ingredients_text="[재료] 돼지고기 300 g | 두부 1 개",
        raw_servings_text="2인분",
        household_size=4,
    )

    # household_size 4 / recipe_servings 2 = 2배로 환산 -> 돼지고기 600g * 20원 = 12000
    # 두부는 "개" 단위라 환산 없이 캐시된 단위가(포장당) 그대로 1개 몫만 반영
    assert result["known_total"] == 12000 + 1500
    assert result["priced_count"] == 2
    assert result["total_count"] == 2
    assert result["unknown_ingredients"] == []


def test_estimate_recipe_price_reports_unknown_ingredients(monkeypatch):
    monkeypatch.setattr(ingredient_price_cache, "get_unit_prices", lambda pairs, max_age_days=7.0: {})

    result = price_estimate.estimate_recipe_price(
        raw_ingredients_text="[재료] 희귀재료 100 g",
        raw_servings_text="1인분",
        household_size=1,
    )

    assert result["known_total"] == 0
    assert result["priced_count"] == 0
    assert result["unknown_ingredients"] == ["희귀재료"]
