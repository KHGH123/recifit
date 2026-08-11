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
