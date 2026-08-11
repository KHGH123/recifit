import json

from recifit_agent import kurly_client


class _FakeResponse:
    def __init__(self, *, json_data=None, text=""):
        self._json_data = json_data
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _search_payload(items):
    return {"data": {"listSections": [{"view": {"sectionCode": "PRODUCT_LIST"}, "data": {"items": items}}]}}


def test_search_products_excludes_sold_out_and_picks_discounted_price(monkeypatch):
    items = [
        {"no": 1, "name": "돼지고기 앞다리 300g", "salesPrice": 9490, "discountedPrice": 7990, "discountRate": 15.0, "isSoldOut": False, "deliveryTypeNames": ["샛별배송"]},
        {"no": 2, "name": "품절된 고기 300g", "salesPrice": 5000, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": True, "deliveryTypeNames": []},
    ]

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data=_search_payload(items))

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    result = kurly_client.search_products("돼지고기")
    assert len(result["results"]) == 1
    product = result["results"][0]
    assert product["product_id"] == "1"
    assert product["price"] == 7990
    assert product["original_price"] == 9490
    assert product["pkg_amount"] == 300.0
    assert product["pkg_unit"] == "g"
    assert product["vendor"] == "컬리"
    assert product["url"] == "https://www.kurly.com/goods/1"


def test_search_products_falls_back_to_sales_price_when_not_discounted(monkeypatch):
    items = [{"no": 3, "name": "참기름 180ml", "salesPrice": 8900, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": False, "deliveryTypeNames": []}]

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data=_search_payload(items))

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    result = kurly_client.search_products("참기름")
    assert result["results"][0]["price"] == 8900
    assert result["results"][0]["pkg_amount"] == 180.0
    assert result["results"][0]["pkg_unit"] == "ml"


def test_search_products_missing_pkg_amount_when_no_unit_in_name(monkeypatch):
    items = [{"no": 4, "name": "제주도 돼지고기 골라담기 11종, 택1", "salesPrice": 14900, "discountedPrice": 10990, "discountRate": 26.0, "isSoldOut": False, "deliveryTypeNames": []}]

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data=_search_payload(items))

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    result = kurly_client.search_products("돼지고기")
    assert result["results"][0]["pkg_amount"] is None
    assert result["results"][0]["pkg_unit"] is None


def test_search_products_caps_results_at_max_results(monkeypatch):
    items = [
        {"no": i, "name": f"상품{i} 300g", "salesPrice": 1000, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": False, "deliveryTypeNames": []}
        for i in range(20)
    ]

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data=_search_payload(items))

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    result = kurly_client.search_products("상품", max_results=3)
    assert len(result["results"]) == 3


def test_search_products_max_results_skips_sold_out_without_counting_them(monkeypatch):
    items = [
        {"no": 1, "name": "품절1 300g", "salesPrice": 1000, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": True, "deliveryTypeNames": []},
        {"no": 2, "name": "재고2 300g", "salesPrice": 1000, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": False, "deliveryTypeNames": []},
        {"no": 3, "name": "재고3 300g", "salesPrice": 1000, "discountedPrice": None, "discountRate": 0.0, "isSoldOut": False, "deliveryTypeNames": []},
    ]

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data=_search_payload(items))

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    result = kurly_client.search_products("재고", max_results=2)
    ids = [p["product_id"] for p in result["results"]]
    assert ids == ["2", "3"]


def test_count_products_returns_count(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(json_data={"data": {"count": 521}})

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    assert kurly_client.count_products("돼지고기") == {"count": 521}


def test_get_product_detail_parses_next_data(monkeypatch):
    next_data = {
        "props": {
            "pageProps": {
                "product": {
                    "no": 1002040323,
                    "name": "제주도 돼지고기 앞다리 찌개용 300g(냉장)",
                    "basePrice": 7990,
                    "retailPrice": 9490,
                    "discountedPrice": None,
                    "discountRate": 15,
                    "volume": "300g",
                    "unitPriceText": "100g 당 2,663원",
                    "storageTypes": ["COLD"],
                    "deliveryTypeNames": ["샛별배송"],
                }
            }
        }
    }
    html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></body></html>'

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(text=html)

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    detail = kurly_client.get_product_detail("1002040323")
    assert detail["price"] == 7990
    assert detail["original_price"] == 9490
    assert detail["pkg_amount"] == 300.0
    assert detail["pkg_unit"] == "g"
    assert detail["url"] == "https://www.kurly.com/goods/1002040323"


def test_get_product_detail_missing_next_data_returns_error(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(text="<html><body>no data here</body></html>")

    monkeypatch.setattr(kurly_client.requests, "get", fake_get)

    detail = kurly_client.get_product_detail("999")
    assert "error" in detail
