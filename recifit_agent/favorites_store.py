"""Firestore-backed cache for previously computed grocery-cart results.

Keyed by (recipe_id + user conditions: household size, budget, excluded
items). The [B-2] product-search step calls product_search_agent once per
ingredient against the live Kurly API, which can take minutes for a recipe
with many ingredients — this cache lets the web frontend skip re-running
that whole loop when the exact same recipe+conditions combo was already
computed, instead of re-invoking the agent.

The Firestore client is created lazily (not at import time, unlike
discovery_engine_client.py) because this module is imported by server.py
before the agent package's .env has been loaded — GOOGLE_CLOUD_PROJECT
isn't reliably set yet at import time.
"""
import os

from google.cloud import firestore

_COLLECTION = "recifit_cart_cache"
_client: firestore.Client | None = None


def _get_client() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    return _client


def _safe_doc_id(cache_key: str) -> str:
    # Firestore document IDs can't contain "/"; conditions are joined with
    # "|" precisely to avoid this, but sanitize defensively anyway.
    return cache_key.replace("/", "_")


def get_cached_result(cache_key: str) -> dict | None:
    doc = _get_client().collection(_COLLECTION).document(_safe_doc_id(cache_key)).get()
    return doc.to_dict() if doc.exists else None


def save_cached_result(cache_key: str, data: dict) -> None:
    _get_client().collection(_COLLECTION).document(_safe_doc_id(cache_key)).set(
        {**data, "updated_at": firestore.SERVER_TIMESTAMP}
    )


# ---------------------------------------------------------------------------
# 사용자가 직접 "즐겨찾기"한 레시피 — 위 자동 캐시와 달리 명시적으로 저장한
# 것만 들어가고, 나중에 목록으로 다시 볼 수 있어야 한다. 같은 기기에서
# 같은 레시피를 같은 조건으로 다시 즐겨찾기하면 새 항목을 만들지 않고
# 기존 것을 덮어쓰도록(idempotent) 결정론적 문서 ID를 쓴다.
# ---------------------------------------------------------------------------
_FAVORITES_COLLECTION = "recifit_favorite_recipes"


def _favorite_doc_id(device_id: str, recipe_id: str, household_size, budget, excluded_items: list[str]) -> str:
    excluded_key = ",".join(sorted(excluded_items or []))
    raw = f"{device_id}__{recipe_id}__h{household_size}__b{budget or 'none'}__e{excluded_key}"
    return _safe_doc_id(raw)


def list_favorite_recipes(device_id: str) -> list[dict]:
    docs = _get_client().collection(_FAVORITES_COLLECTION).where("device_id", "==", device_id).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    # where + order_by 조합은 복합 색인이 필요해서, 정렬은 그냥 여기서 한다
    # (기기당 즐겨찾기 개수가 색인이 필요할 만큼 많을 일은 없다).
    results.sort(key=lambda d: d.get("created_at") or 0, reverse=True)
    return results


def save_favorite_recipe(device_id: str, favorite: dict) -> str:
    doc_id = _favorite_doc_id(
        device_id,
        favorite.get("recipe_id"),
        favorite.get("household_size"),
        favorite.get("budget"),
        favorite.get("excluded_items"),
    )
    doc_ref = _get_client().collection(_FAVORITES_COLLECTION).document(doc_id)
    doc_ref.set({**favorite, "device_id": device_id, "created_at": firestore.SERVER_TIMESTAMP}, merge=True)
    return doc_id


def delete_favorite_recipe(device_id: str, favorite_id: str) -> bool:
    doc_ref = _get_client().collection(_FAVORITES_COLLECTION).document(favorite_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("device_id") != device_id:
        return False
    doc_ref.delete()
    return True
