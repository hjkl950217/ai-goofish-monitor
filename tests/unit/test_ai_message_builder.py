import json

from src.infrastructure.external.ai_client import AIClient


def test_analysis_messages_exclude_previous_conclusion_without_mutating_record():
    record = {
        "item_info": {"title": "九号N1 90", "price": "¥5000"},
        "seller_info": {"seller_credit_level": "优秀"},
        "ai_analysis": {"reason": "OLD_CONCLUSION_DO_NOT_REUSE", "value_score": 99},
    }
    client = AIClient.__new__(AIClient)

    content = client._build_messages(record, [], "核对目标型号")[0]["content"]

    assert "九号N1 90" in content
    assert "优秀" in content
    assert "OLD_CONCLUSION_DO_NOT_REUSE" not in content
    assert '"ai_analysis"' not in content
    assert record["ai_analysis"]["value_score"] == 99


def test_unverified_search_prices_are_not_sent_as_reliable_market_reference():
    record = {
        "item_info": {"title": "九号N1 90", "price": "¥5000"},
        "price_reference": {"当前搜索样本": {"median_price": 50}},
        "price_insight": {"market_median_price": 50, "deal_score": 0},
    }
    client = AIClient.__new__(AIClient)

    content = client._build_messages(record, [], "评估性价比")[0]["content"]

    assert '"market_median_price": 50' not in content
    assert '"deal_score": 0' not in content
    assert '"median_price": 50' not in content
    assert record["price_insight"]["market_median_price"] == 50
