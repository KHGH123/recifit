from recifit_agent.ingredient_price_cache import _merge_stats, normalize_ingredient_name


def test_normalize_ingredient_name_strips_whitespace_and_case():
    assert normalize_ingredient_name("  돼지고기  앞다리 ") == "돼지고기앞다리"
    assert normalize_ingredient_name("Milk") == "milk"


def test_merge_stats_from_empty_starts_fresh():
    avg, lo, hi, count = _merge_stats(0.0, None, None, 0, [10.0, 20.0, 30.0])
    assert avg == 20.0
    assert lo == 10.0
    assert hi == 30.0
    assert count == 3


def test_merge_stats_blends_into_existing_average():
    # 기존에 2개(평균 10)가 있는 상태에서 20 하나를 더 관측하면
    # 평균은 (10*2 + 20) / 3으로 옮겨가야 한다.
    avg, lo, hi, count = _merge_stats(10.0, 5.0, 15.0, 2, [20.0])
    assert avg == 40.0 / 3
    assert lo == 5.0
    assert hi == 20.0
    assert count == 3
