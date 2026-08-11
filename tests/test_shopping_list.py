from recifit_agent import shopping_list


def _kurly_result(product_id, price, pkg_amount, pkg_unit, name):
    return {
        "product_id": product_id,
        "name": name,
        "price": price,
        "original_price": price,
        "discount_rate": 0,
        "delivery_types": [],
        "pkg_amount": pkg_amount,
        "pkg_unit": pkg_unit,
        "vendor": "컬리",
        "url": f"https://www.kurly.com/goods/{product_id}",
    }


def test_build_shopping_list_scales_searches_and_sums(monkeypatch):
    def fake_search_products(name):
        if name == "돼지고기":
            return {"results": [_kurly_result("p1", 5000, 300, "g", "돼지고기 300g")]}
        if name == "두부":
            return {"results": [_kurly_result("p2", 1500, 1, "개", "두부 1모")]}
        return {"results": []}

    monkeypatch.setattr(shopping_list, "search_products", fake_search_products)
    monkeypatch.setattr(shopping_list, "record_price_observations", lambda *a, **k: None)

    ingredients = [
        {"name": "돼지고기", "amount": 300, "unit": "g", "raw": "돼지고기 300g"},
        {"name": "두부", "amount": None, "unit": None, "raw": "두부 1모"},
    ]

    result = shopping_list.build_shopping_list(
        ingredients=ingredients,
        recipe_servings=2,
        household_size=4,
        exclude_terms=[],
        budget=15000,
        meal_count=1,
    )

    assert len(result["selections"]) == 2
    pork = result["selections"][0]
    assert pork["ingredient"] == "돼지고기"
    assert pork["scaled_amount"] == 600.0
    assert pork["quantity"] == 2
    assert pork["subtotal"] == 10000

    tofu = result["selections"][1]
    assert tofu["selected"]["product_id"] == "p2"

    assert result["total_price"] == 11500
    assert result["within_budget"] is True


def test_build_shopping_list_excludes_allergy_terms_from_products(monkeypatch):
    def fake_search_products(name):
        return {"results": [_kurly_result("p1", 4000, 200, "g", "냉동 새우 200g")]}

    monkeypatch.setattr(shopping_list, "search_products", fake_search_products)
    monkeypatch.setattr(shopping_list, "record_price_observations", lambda *a, **k: None)

    result = shopping_list.build_shopping_list(
        ingredients=[{"name": "새우", "amount": 200, "unit": "g", "raw": "새우 200g"}],
        recipe_servings=1,
        household_size=1,
        exclude_terms=["새우"],
    )

    assert result["selections"][0]["selected"] is None
    assert result["selections"][0]["skipped_reason"] is not None
    assert result["total_price"] == 0


def test_build_shopping_list_handles_no_search_results(monkeypatch):
    monkeypatch.setattr(shopping_list, "search_products", lambda name: {"results": []})

    result = shopping_list.build_shopping_list(
        ingredients=[{"name": "희귀재료", "amount": 100, "unit": "g", "raw": "희귀재료 100g"}],
        recipe_servings=1,
        household_size=1,
        exclude_terms=[],
    )

    assert result["selections"][0]["selected"] is None
    assert result["total_price"] == 0
    assert result["within_budget"] is None


def test_build_shopping_list_caches_all_candidates_not_just_the_picked_one(monkeypatch):
    # 나중에 [A]단계 예상가(estimate_recipe_price)가 실제 시세에 가깝게
    # 계산되려면, 고른 최저가 상품 하나가 아니라 검색된 후보 전체의
    # 단위가격이 캐시에 반영돼야 한다.
    monkeypatch.setattr(
        shopping_list,
        "search_products",
        lambda name: {
            "results": [
                _kurly_result("p1", 5000, 300, "g", "돼지고기 300g"),
                _kurly_result("p2", 9000, 600, "g", "돼지고기 600g"),
            ]
        },
    )
    recorded = []
    monkeypatch.setattr(
        shopping_list,
        "record_price_observations",
        lambda name, unit, prices, sample_name=None, reset=False: recorded.append((name, unit, prices)),
    )

    shopping_list.build_shopping_list(
        ingredients=[{"name": "돼지고기", "amount": 300, "unit": "g", "raw": "돼지고기 300g"}],
        recipe_servings=2,
        household_size=2,
        exclude_terms=[],
    )

    assert len(recorded) == 1
    name, unit, prices = recorded[0]
    assert name == "돼지고기"
    assert unit == "g"
    assert sorted(prices) == sorted([5000 / 300, 9000 / 600])
