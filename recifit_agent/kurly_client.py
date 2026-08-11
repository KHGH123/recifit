"""Direct (non-LLM) calls to Kurly's public search/detail endpoints.

Same rationale as discovery_engine_client.py/recipe_detail_client.py: prices,
ids and stock status must be plain field values the model copies, not
numbers it reads out of prose and might transcribe wrong. These functions
are used directly as agent tools (like recipe_detail_client.get_recipe),
so their docstrings double as the tool descriptions the model sees.
"""
import json
import re

import requests
from bs4 import BeautifulSoup

_SEARCH_URL = "https://api.kurly.com/search/v4/sites/market/normal-search"
_COUNT_URL = "https://api.kurly.com/search/v3/sites/market/normal-search/count"
_GOODS_URL = "https://www.kurly.com/goods/{product_id}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

# Kurly product names/volume strings embed the package size like "300g" or
# "1.5L"; pkg_amount/pkg_unit are pulled from that with this regex rather
# than trusting the model to read it out of the name. Units outside this
# set (e.g. "개", "6입") fall back to pkg_amount=None, which cart_tools.py
# already treats as "assume one package" — same tolerance as the recipe
# ingredient parser.
_AMOUNT_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", re.IGNORECASE)


def _parse_pkg_amount(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    match = _AMOUNT_UNIT_RE.search(text)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2).lower()


def search_products(keyword: str, page: int = 1, max_results: int = 10) -> dict:
    """마켓컬리에서 키워드로 상품을 검색한다(장보기용 실시간 검색).

    결과의 product_id, price, pkg_amount, pkg_unit, vendor, url은 전부 실제
    값이니 그대로 사용해라 — 가격이나 용량을 스스로 만들어내지 않는다.
    품절 상품은 결과에서 이미 제외되어 있다. 대용량 상품이 더 저렴한지
    비교할 수 있도록, 소용량과 대용량 후보가 섞여 나올 만큼(기본 10개)
    넉넉히 반환한다.

    Args:
        keyword: 검색할 재료/상품명 (예: "돼지고기 앞다리").
        page: 검색 결과 페이지 번호(1부터 시작).
        max_results: 반환할 최대 후보 개수.

    Returns:
        {"results": [{product_id, name, price, original_price, discount_rate,
        delivery_types, pkg_amount, pkg_unit, vendor, url}, ...]} 형태의 dict.
        가격/재고 정보는 조회 시점 기준 참고값이다.
    """
    response = requests.get(
        _SEARCH_URL,
        params={"keyword": keyword, "page": page},
        headers=_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    items = []
    for section in payload.get("data", {}).get("listSections", []):
        if section.get("view", {}).get("sectionCode") != "PRODUCT_LIST":
            continue
        items.extend(section.get("data", {}).get("items", []))

    results = []
    for item in items:
        if len(results) >= max_results:
            break
        if item.get("isSoldOut"):
            continue
        product_id = str(item.get("no"))
        name = item.get("name")
        price = item.get("discountedPrice") or item.get("salesPrice")
        pkg_amount, pkg_unit = _parse_pkg_amount(name)
        results.append(
            {
                "product_id": product_id,
                "name": name,
                "price": price,
                "original_price": item.get("salesPrice"),
                "discount_rate": item.get("discountRate"),
                "delivery_types": item.get("deliveryTypeNames", []),
                "pkg_amount": pkg_amount,
                "pkg_unit": pkg_unit,
                "vendor": "컬리",
                "url": _GOODS_URL.format(product_id=product_id),
            }
        )
    return {"results": results}


def count_products(keyword: str) -> dict:
    """마켓컬리에서 키워드의 전체 검색 결과 개수를 조회한다.

    검색어가 너무 포괄적이어서(예: "고기") 결과가 지나치게 많을 것 같을 때,
    실제 상품 후보를 다 가져오기 전에 규모를 먼저 확인하는 용도다. 개수가
    아주 많으면 더 구체적인 검색어로 다시 search_products를 호출하는 게 좋다.

    Args:
        keyword: 검색할 재료/상품명.

    Returns:
        {"count": int} 형태의 dict.
    """
    response = requests.get(
        _COUNT_URL,
        params={"keyword": keyword, "filters": "", "allow_replace": "true"},
        headers=_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    count = response.json().get("data", {}).get("count", 0)
    return {"count": count}


def get_product_detail(product_id: str) -> dict:
    """마켓컬리 상품 상세 페이지에서 보조 정보를 확인한다.

    search_products 결과만으로 판단이 애매한 상품(예: pkg_amount를 못 읽어
    수량 계산이 불확실한 경우)이 있을 때만 그 상품 하나를 추가로 확인하는
    용도다 — 후보마다 매번 호출할 필요는 없다.

    Args:
        product_id: search_products가 돌려준 product_id.

    Returns:
        {product_id, name, price, original_price, discount_rate, pkg_amount,
        pkg_unit, unit_price_text, storage_types, delivery_types, url} 형태의
        dict. 상세 정보를 찾을 수 없으면 {"error": ...}.
    """
    url = _GOODS_URL.format(product_id=product_id)

    try:
        response = requests.get(url, headers=_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": f"상품 페이지를 불러오지 못했습니다: {exc}"}

    soup = BeautifulSoup(response.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return {"error": "상품 상세 정보를 찾을 수 없습니다."}

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return {"error": "상품 상세 정보를 파싱하지 못했습니다."}

    product = data.get("props", {}).get("pageProps", {}).get("product")
    if not product:
        return {"error": "상품 상세 정보를 찾을 수 없습니다."}

    pkg_amount, pkg_unit = _parse_pkg_amount(product.get("volume") or product.get("name"))

    return {
        "product_id": str(product.get("no", product_id)),
        "name": product.get("name"),
        "price": product.get("discountedPrice") or product.get("basePrice"),
        "original_price": product.get("retailPrice"),
        "discount_rate": product.get("discountRate"),
        "pkg_amount": pkg_amount,
        "pkg_unit": pkg_unit,
        "unit_price_text": product.get("unitPriceText"),
        "storage_types": product.get("storageTypes", []),
        "delivery_types": product.get("deliveryTypeNames", []),
        "url": url,
    }
