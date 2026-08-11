"""Firestore-backed cache of real per-unit ingredient prices, built up from
build_shopping_list's own live Kurly results.

The [A]-stage rough price estimate (root_agent step 3) used to be a pure LLM
guess with no grounding in real prices, which is why it routinely diverged
a lot from the [B-2] stage's real computed total. Calling Kurly live for
every ingredient of every candidate would reintroduce the exact per-
ingredient latency we already eliminated (shopping_list.py), and a public
price API/dataset was ruled out separately (see project notes: coverage
gap for processed/seasoning ingredients). Instead this cache accumulates
real unit prices opportunistically: every time build_shopping_list searches
an ingredient for a real user, *all* of that search's results (not just the
one picked) get folded in here as price observations. estimate_recipe_price
then reads straight from Firestore (fast, no live HTTP calls) for a much
more grounded [A]-stage estimate, only asking the model to guess for
ingredients it has never priced.

Prices drift, so a cache entry isn't trusted forever: get_unit_prices
ignores anything older than max_age_days (treated the same as "never
cached"), and scripts/seed_ingredient_price_cache.py can be re-run with
--refresh to replace stale entries with fresh live searches rather than
silently blending old prices into the average forever.
"""
import os
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

_COLLECTION = "recifit_ingredient_price_cache"
_DEFAULT_MAX_AGE_DAYS = 7.0
_client: firestore.Client | None = None


def _get_client() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    return _client


def normalize_ingredient_name(name: str) -> str:
    # 공백/대소문자 차이만 정리한다 — "다진", "채썬" 같은 수식어까지
    # 걷어내면 서로 다른 재료가 같은 캐시 항목으로 뭉쳐버릴 수 있다.
    return "".join(str(name or "").split()).lower()


def _doc_id(name: str, unit: str) -> str:
    key = f"{normalize_ingredient_name(name)}__{unit}"
    return key.replace("/", "_") or "_empty"


def _merge_stats(
    old_avg: float, old_min: float | None, old_max: float | None, old_count: int, prices: list[float]
) -> tuple[float, float, float, int]:
    new_count = old_count + len(prices)
    new_avg = (old_avg * old_count + sum(prices)) / new_count
    min_candidates = prices + ([old_min] if old_min is not None else [])
    max_candidates = prices + ([old_max] if old_max is not None else [])
    return new_avg, min(min_candidates), max(max_candidates), new_count


def get_unit_prices(
    name_unit_pairs: list[tuple[str, str]], max_age_days: float = _DEFAULT_MAX_AGE_DAYS
) -> dict[tuple[str, str], dict]:
    """(재료명, 기본단위) 목록에 대해 캐시된 단위가격을 한 번에 조회한다.

    max_age_days보다 오래된 항목은 결과에서 아예 뺀다 — 오래된 가격을
    그대로 믿고 쓰지 않기 위함이며, 이 경우 호출한 쪽은 "캐시에 없음"과
    동일하게 취급하면 된다.

    Returns:
        (재료명, 단위) -> {avg_unit_price, min_unit_price, max_unit_price,
        sample_count, sample_product_name} 형태의 dict. 없거나 오래된
        항목은 키 자체가 없다.
    """
    pairs = [(name, unit) for name, unit in name_unit_pairs if name and unit]
    if not pairs:
        return {}

    client = _get_client()
    refs = [client.collection(_COLLECTION).document(_doc_id(name, unit)) for name, unit in pairs]
    snapshots = {snap.id: snap for snap in client.get_all(refs)}

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    result: dict[tuple[str, str], dict] = {}
    for name, unit in pairs:
        snap = snapshots.get(_doc_id(name, unit))
        if snap is None or not snap.exists:
            continue
        data = snap.to_dict()
        updated_at = data.get("updated_at")
        if updated_at is not None and updated_at < cutoff:
            continue
        result[(name, unit)] = data
    return result


def record_price_observations(
    name: str,
    unit: str,
    prices: list[float],
    sample_product_name: str | None = None,
    reset: bool = False,
) -> None:
    """재료의 실제 관측된 단위가격들을 캐시에 반영한다.

    reset=False(기본값, build_shopping_list가 실사용 중 호출)면 기존
    평균에 새 관측치를 누적해서 섞는다. reset=True(재시딩/갱신 스크립트
    전용)면 기존 값을 버리고 이번 관측치로 완전히 새로 계산한다 — 오래된
    가격이 평균에 영영 남아있지 않도록, 최신 실검색 결과로 통째로
    갈아치우는 용도다.
    """
    if not name or not unit or not prices:
        return

    doc_ref = _get_client().collection(_COLLECTION).document(_doc_id(name, unit))
    existing = None
    if not reset:
        snapshot = doc_ref.get()
        existing = snapshot.to_dict() if snapshot.exists else None

    old_count = existing.get("sample_count", 0) if existing else 0
    old_avg = existing.get("avg_unit_price", 0.0) if existing else 0.0
    old_min = existing.get("min_unit_price") if existing else None
    old_max = existing.get("max_unit_price") if existing else None

    new_avg, new_min, new_max, new_count = _merge_stats(old_avg, old_min, old_max, old_count, prices)

    doc_ref.set(
        {
            "ingredient_name": name,
            "unit": unit,
            "avg_unit_price": round(new_avg, 2),
            "min_unit_price": new_min,
            "max_unit_price": new_max,
            "sample_count": new_count,
            "sample_product_name": sample_product_name,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
    )


def list_all_cached_names() -> list[tuple[str, str]]:
    """캐시에 이미 들어있는 (재료명, 단위) 전체 목록 — 갱신 스크립트 전용."""
    docs = _get_client().collection(_COLLECTION).stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        name, unit = data.get("ingredient_name"), data.get("unit")
        if name and unit:
            result.append((name, unit))
    return result
