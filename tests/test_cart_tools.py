from recifit_agent.cart_tools import pick_cheapest_product, scale_ingredient_amount, summarize_cart


def _product(product_id, price, pkg_amount=None, pkg_unit=None, name="상품"):
    return {
        "product_id": product_id,
        "name": name,
        "price": price,
        "pkg_amount": pkg_amount,
        "pkg_unit": pkg_unit,
        "vendor": "테스트",
        "url": "https://example.invalid",
    }


def test_scale_ingredient_amount_scales_by_household_ratio():
    result = scale_ingredient_amount(amount=300, recipe_servings=2, household_size=4)
    assert result["scale_factor"] == 2.0
    assert result["scaled_amount"] == 600.0


def test_scale_ingredient_amount_handles_none_amount():
    result = scale_ingredient_amount(amount=None, recipe_servings=2, household_size=4)
    assert result["scaled_amount"] is None


def test_pick_cheapest_product_chooses_lowest_total_cost():
    candidates = [
        _product("p1", price=8000, pkg_amount=300, pkg_unit="g", name="비싼 돼지고기 300g"),
        _product("p2", price=5000, pkg_amount=300, pkg_unit="g", name="저렴한 돼지고기 300g"),
    ]
    result = pick_cheapest_product(needed_amount=600, needed_unit="g", candidates=candidates, exclude_terms=[])
    assert result["selected"]["product_id"] == "p2"
    assert result["quantity"] == 2
    assert result["subtotal"] == 10000


def test_pick_cheapest_product_prefers_bulk_size_when_cheaper_per_unit():
    candidates = [
        _product("p_small", price=3000, pkg_amount=300, pkg_unit="g", name="소용량 300g"),  # need 4x -> 12000
        _product("p_bulk", price=9000, pkg_amount=1200, pkg_unit="g", name="대용량 1.2kg"),  # need 1x -> 9000
    ]
    result = pick_cheapest_product(needed_amount=1200, needed_unit="g", candidates=candidates, exclude_terms=[])
    assert result["selected"]["product_id"] == "p_bulk"
    assert result["subtotal"] == 9000


def test_pick_cheapest_product_excludes_allergy_terms():
    candidates = [_product("p1", price=4000, pkg_amount=200, pkg_unit="g", name="냉동 새우 200g")]
    result = pick_cheapest_product(needed_amount=200, needed_unit="g", candidates=candidates, exclude_terms=["새우"])
    assert result["selected"] is None
    assert result["skipped_reason"] is not None


def test_summarize_cart_sums_and_checks_budget():
    selections = [{"subtotal": 5000}, {"subtotal": 3000}]
    result = summarize_cart(selections, budget=10000)
    assert result["total_price"] == 8000
    assert result["within_budget"] is True

    result_over = summarize_cart(selections, budget=5000)
    assert result_over["within_budget"] is False
