"""Seeds/refreshes recifit_ingredient_price_cache with real Kurly searches.

estimate_recipe_price (recifit_agent/price_estimate.py) never calls Kurly
live — it only reads whatever's already cached. That cache fills up
organically as real users go through [B-2] (build_shopping_list), but a
fresh deployment starts empty, and prices drift over time. This script
covers both:

    python scripts/seed_ingredient_price_cache.py             # bootstrap: search ~50 common ingredients
    python scripts/seed_ingredient_price_cache.py --refresh   # re-search everything already cached

Both modes do real (reset=True) searches, replacing whatever was cached
for that ingredient rather than blending in stale numbers. Run manually,
or wire to a scheduler (e.g. Cloud Scheduler -> Cloud Run Job) with
--refresh if the cache should stay current without someone remembering to
run this by hand.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recifit_agent", ".env"))

from recifit_agent import ingredient_price_cache  # noqa: E402
from recifit_agent.cart_tools import to_base_unit  # noqa: E402
from recifit_agent.kurly_client import search_products  # noqa: E402

# 흔히 쓰이는 한식/양식/중식 레시피 재료 — 이걸로 배포 첫날부터 [A]단계
# 예상가가 어느 정도 실제 시세를 반영하게 한다. 목록을 다 채우는 게
# 목적이 아니라, 실사용으로 캐시가 자연스럽게 채워지기 전까지의
# 최소한의 커버리지를 확보하는 용도다.
_COMMON_INGREDIENTS = [
    "돼지고기 앞다리", "돼지고기 삼겹살", "돼지고기 목살", "소고기 등심", "소고기 불고기용",
    "닭가슴살", "닭다리살", "닭볼살",
    "대파", "양파", "마늘", "다진마늘", "생강", "감자", "당근", "애호박", "고구마",
    "두부", "계란", "김치", "콩나물", "숙주나물", "시금치", "느타리버섯", "표고버섯", "양배추",
    "간장", "고추장", "된장", "설탕", "소금", "식용유", "참기름", "고춧가루", "후추",
    "맛술", "굴소스", "케찹", "마요네즈", "밀가루", "부침가루", "전분가루",
    "우유", "치즈", "베이컨", "스팸", "어묵", "떡볶이떡", "라면사리",
    "쌀", "국수", "당면", "미역", "멸치", "다시마", "새우", "오징어", "참치캔",
]


def _search_and_record(name: str) -> int:
    results = search_products(name, max_results=10).get("results", [])

    buckets: dict[str, list[float]] = {}
    sample_names: dict[str, str] = {}
    for item in results:
        price = item.get("price")
        if price is None:
            continue
        base = to_base_unit(item.get("pkg_amount"), item.get("pkg_unit"))
        if base:
            base_amount, unit = base
            if not base_amount:
                continue
            unit_price = price / base_amount
        else:
            unit, unit_price = "개", price
        buckets.setdefault(unit, []).append(unit_price)
        sample_names.setdefault(unit, item.get("name"))

    for unit, prices in buckets.items():
        ingredient_price_cache.record_price_observations(name, unit, prices, sample_names.get(unit), reset=True)
    return len(results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="새 재료 대신, 이미 캐시된 재료 전체를 다시 검색해서 갱신")
    args = parser.parse_args()

    if args.refresh:
        names = sorted({name for name, _unit in ingredient_price_cache.list_all_cached_names()})
        print(f"캐시된 재료 {len(names)}개 갱신 시작")
    else:
        names = _COMMON_INGREDIENTS
        print(f"기본 재료 {len(names)}개 시딩 시작")

    for name in names:
        try:
            count = _search_and_record(name)
            print(f"  {name}: 상품 {count}개 반영")
        except Exception as exc:
            print(f"  {name}: 실패 ({exc})")


if __name__ == "__main__":
    main()
