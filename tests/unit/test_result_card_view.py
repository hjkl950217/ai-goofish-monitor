import json

from src.services.result_card_view import compact_card_record


def _record():
    return {
        "crawl_time": "2026-10-30T09:00:00",
        "keyword": "九号M1",
        "task_name": "t1",
        "item_info": {
            "item_id": "111",
            "title": "九号M1 100 准新车",
            "price": "¥5720",
            "original_price": "¥6799",
            "want_count": 31,
            "view_count": 1232,
            "tags": ["包邮"],
            "shipping_area": "新都区",
            "seller_nickname": "卖家",
            "link": "https://www.goofish.com/item?id=111",
            "publish_time": "2026-09-30 18:34",
            "images": ["https://img.alicdn.com/a.jpg", "https://img.alicdn.com/b.jpg"],
            "main_image": "https://img.alicdn.com/a.jpg",
            "description": "很长的描述" * 50,
        },
        "seller_info": {
            "seller_nickname": "卖家",
            "seller_listing_counts": "198",
            "seller_credit_level": "极好",
            "seller_items": [
                {"status": "在售", "title": "x" * 200},
                {"status": "在售", "title": "x" * 200},
                {"status": "已售", "title": "x" * 200},
            ],
            "seller_ratings": [{"comment": "y" * 200}],
            "seller_bio": "z" * 100,
        },
        "ai_analysis": {
            "is_recommended": False,
            "reason": "车贩子",
            "value_score": 42,
            "criteria_analysis": {"model_chip": {"status": "NEEDS_MANUAL_CHECK", "comment": "w" * 200}},
        },
        "price_reference": {"当前搜索样本": {"avg_price": 5236.4}},
        "price_insight": {"observation_count": 5, "market_avg_price": 6082.71, "min_price": 5720},
        "_status": "active",
        "_initial_price": 5720.0,
        "_current_price": 5720.0,
        "_effective_hidden": False,
        "_meta": {"result_filename": "九号M1_100_full_data.jsonl"},
    }


def test_drops_fields_the_card_never_shows():
    out = compact_card_record(_record())

    assert "description" not in out["item_info"]
    assert "images" not in out["item_info"]
    assert "seller_items" not in out["seller_info"]
    assert "seller_ratings" not in out["seller_info"]
    assert "seller_bio" not in out["seller_info"]
    assert "criteria_analysis" not in out["ai_analysis"]
    assert "price_reference" not in out


def test_keeps_fields_the_card_renders():
    out = compact_card_record(_record())

    item = out["item_info"]
    for key in ("item_id", "title", "price", "original_price", "want_count",
                "view_count", "tags", "shipping_area", "link", "publish_time", "main_image"):
        assert key in item, key
    assert out["seller_info"]["seller_credit_level"] == "极好"
    assert out["seller_info"]["seller_listing_counts"] == "198"
    assert out["ai_analysis"]["reason"] == "车贩子"
    assert out["ai_analysis"]["value_score"] == 42
    assert out["price_insight"]["market_avg_price"] == 6082.71
    assert out["_meta"]["result_filename"] == "九号M1_100_full_data.jsonl"
    assert out["_current_price"] == 5720.0


def test_listing_counts_replaced_by_two_numbers():
    out = compact_card_record(_record())
    assert out["seller_info"]["on_sale_count"] == 2
    assert out["seller_info"]["sold_count"] == 1


def test_no_counts_when_no_listing_details():
    record = _record()
    record["seller_info"].pop("seller_items")
    out = compact_card_record(record)
    assert "on_sale_count" not in out["seller_info"]


def test_main_image_pointed_at_thumbnail_proxy():
    out = compact_card_record(_record())
    assert out["item_info"]["main_image"].startswith("/api/images/thumb?src=")
    assert out["item_info"]["main_image"].endswith("&w=480")


def test_custom_width_and_missing_image():
    out = compact_card_record(_record(), image_width=240)
    assert out["item_info"]["main_image"].endswith("&w=240")

    record = _record()
    record["item_info"].pop("main_image")
    assert "main_image" not in compact_card_record(record)["item_info"]


def test_source_record_not_mutated():
    record = _record()
    before = json.dumps(record, ensure_ascii=False, sort_keys=True)
    compact_card_record(record)
    assert json.dumps(record, ensure_ascii=False, sort_keys=True) == before


def test_payload_shrinks_a_lot():
    record = _record()
    full = len(json.dumps(record, ensure_ascii=False).encode())
    compact = len(json.dumps(compact_card_record(record), ensure_ascii=False).encode())
    assert compact * 3 < full
