from src.services.price_history_service import (
    _summarize_prices,
    build_item_price_context,
    build_market_reference,
    build_price_history_insights,
    load_price_snapshots,
    record_market_snapshots,
)


def test_summarize_prices_drops_outliers():
    records = [{"price": price} for price in [5900, 5950, 6000, 6050, 6100, 3]]
    summary = _summarize_prices(records)

    assert summary["outlier_count"] == 1
    assert summary["raw_sample_count"] == 6
    assert summary["sample_count"] == 5
    assert summary["min_price"] == 5900.0


def test_record_market_snapshots_and_build_price_history_insights(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen_item_ids = set()

    run1_items = [
        {
            "item_id": "1001",
            "title": "Sony A7M4 单机",
            "price": "¥10000",
            "tags": ["验货宝"],
            "shipping_area": "上海",
            "seller_nickname": "卖家A",
            "link": "https://www.goofish.com/item?id=1001",
            "publish_time": "2026-01-01 09:00",
        },
        {
            "item_id": "1002",
            "title": "Sony A7M4 套机",
            "price": "¥12000",
            "tags": ["包邮"],
            "shipping_area": "杭州",
            "seller_nickname": "卖家B",
            "link": "https://www.goofish.com/item?id=1002",
            "publish_time": "2026-01-01 10:00",
        },
    ]
    run2_items = [
        {
            "item_id": "1001",
            "title": "Sony A7M4 单机",
            "price": "¥9500",
            "tags": ["验货宝"],
            "shipping_area": "上海",
            "seller_nickname": "卖家A",
            "link": "https://www.goofish.com/item?id=1001",
            "publish_time": "2026-01-02 09:00",
        },
        {
            "item_id": "1003",
            "title": "Sony A7M4 全套",
            "price": "¥13000",
            "tags": ["同城"],
            "shipping_area": "南京",
            "seller_nickname": "卖家C",
            "link": "https://www.goofish.com/item?id=1003",
            "publish_time": "2026-01-02 11:00",
        },
    ]

    inserted_run1 = record_market_snapshots(
        keyword="sony a7m4",
        task_name="Sony A7M4 监控",
        items=run1_items,
        run_id="run-1",
        snapshot_time="2026-01-01T12:00:00",
        seen_item_ids=seen_item_ids,
    )
    assert len(inserted_run1) == 2

    inserted_run2 = record_market_snapshots(
        keyword="sony a7m4",
        task_name="Sony A7M4 监控",
        items=run2_items,
        run_id="run-2",
        snapshot_time="2026-01-02T12:00:00",
        seen_item_ids=set(),
    )
    assert len(inserted_run2) == 2

    snapshots = load_price_snapshots("sony a7m4")
    assert len(snapshots) == 4

    insights = build_price_history_insights("sony a7m4")
    assert insights["market_summary"]["sample_count"] == 2
    assert insights["market_summary"]["avg_price"] == 11250.0
    assert insights["market_summary"]["min_price"] == 9500.0
    assert insights["history_summary"]["unique_items"] == 3
    assert len(insights["daily_trend"]) == 2
    assert insights["daily_trend"][0]["day"] == "2026-01-01"
    assert insights["daily_trend"][1]["day"] == "2026-01-02"

    item_context = build_item_price_context(
        snapshots,
        item_id="1001",
        current_price=9500.0,
    )
    assert item_context["observation_count"] == 2
    assert item_context["min_price"] == 9500.0
    assert item_context["max_price"] == 10000.0
    assert item_context["price_change_amount"] == -500.0
    # 只有同商品自身历史、没有核实过的同类样本时不给估价
    assert item_context["deal_score"] is None
    assert item_context["deal_label"] == "暂无可靠数据"


def test_market_reference_does_not_treat_raw_search_results_as_comparable():
    item = {"item_id": "car", "title": "九号N1 90整车", "price": 5000}
    mixed = [item] + [
        {"item_id": str(i), "title": "九号N1 90配件", "price": 50} for i in range(9)
    ]
    snapshots = [dict(row, run_id="run", snapshot_time="2026-11-01T10:00:00") for row in mixed]
    result = build_market_reference(
        keyword="九号N1 90", item=item, current_market_items=mixed,
        historical_snapshots=snapshots,
    )
    assert result["当前搜索样本"]["sample_count"] == 0
    assert result["本商品价格位置"]["deal_score"] is None


def test_market_reference_uses_only_verified_comparable_items():
    cars = [{"item_id": key, "price": price} for key, price in (("a", 4900), ("b", 5000), ("c", 5100))]
    accessories = [{"item_id": str(i), "price": 50} for i in range(9)]
    snapshots = [dict(row, run_id="run", snapshot_time="2026-11-01T10:00:00") for row in cars + accessories]
    result = build_market_reference(
        keyword="九号N1 90", item=cars[1], current_market_items=cars + accessories,
        historical_snapshots=snapshots, comparable_item_ids={"a", "b", "c"},
    )
    assert result["当前搜索样本"]["sample_count"] == 3
    assert result["当前搜索样本"]["median_price"] == 5000
    assert result["本商品价格位置"]["market_median_price"] == 5000
    assert result["本商品价格位置"]["comparison_verified"] is True
