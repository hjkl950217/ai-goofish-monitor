"""旧数据归一化：中文键记录读出来必须是英文键。"""
import json

from src.infrastructure.persistence.record_keys import normalize_keys
from src.services.result_storage_service import _parse_raw_record


def test_normalize_keys_handles_nested_lists():
    legacy = {
        "商品信息": {
            "商品标题": "x",
            "商品图片列表": ["a", "b"],
            "卖家发布的商品列表": [{"商品ID": "1", "商品状态": "在售"}],
        }
    }

    record = normalize_keys(legacy)

    assert record["item_info"]["title"] == "x"
    assert record["item_info"]["images"] == ["a", "b"]
    assert record["item_info"]["seller_items"][0] == {"item_id": "1", "status": "在售"}


def test_normalize_keys_keeps_english_and_unknown_keys():
    assert normalize_keys({"item_info": {"title": "x"}, "自定义": 1}) == {
        "item_info": {"title": "x"},
        "自定义": 1,
    }


def test_parse_raw_record_converts_legacy_row():
    raw = json.dumps(
        {
            "爬取时间": "2026-01-01T10:00:00",
            "任务名称": "N190",
            "商品信息": {"商品ID": "1", "商品标题": "x", "当前售价": "100"},
            "卖家信息": {"卖家昵称": "s"},
        },
        ensure_ascii=False,
    )

    record = _parse_raw_record(raw, status="active")

    assert record["task_name"] == "N190"
    assert record["item_info"] == {"item_id": "1", "title": "x", "price": "100"}
    assert record["seller_info"] == {"seller_nickname": "s"}
    assert record["_status"] == "active"
