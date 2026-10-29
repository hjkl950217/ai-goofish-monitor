"""
结果导出服务
"""
import csv
from io import StringIO


EXPORT_HEADERS = [
    "任务名称",
    "搜索关键字",
    "商品ID",
    "商品标题",
    "当前售价",
    "发布时间",
    "发货地区",
    "浏览量",
    "想要人数",
    "商品标签",
    "卖家在售数",
    "卖家已售数",
    "卖家昵称",
    "AI是否推荐",
    "分析来源",
    "原因",
    "价格观察次数",
    "价格最低值",
    "价格最高值",
    "市场均价",
    "性价比分数",
    "性价比标签",
    "商品链接",
]


def _listing_counts(seller: dict) -> tuple[int, int]:
    items = seller.get("seller_items") or []
    on_sale = sum(1 for entry in items if isinstance(entry, dict) and entry.get("status") == "在售")
    sold = sum(1 for entry in items if isinstance(entry, dict) and entry.get("status") == "已售")
    return on_sale, sold


def build_results_csv(records: list[dict]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_HEADERS)
    writer.writeheader()

    for record in records:
        item = record.get("item_info", {}) or {}
        seller = record.get("seller_info", {}) or {}
        ai_analysis = record.get("ai_analysis", {}) or {}
        price_insight = record.get("price_insight", {}) or {}
        on_sale, sold = _listing_counts(seller)
        tags = item.get("tags") or []
        writer.writerow(
            {
                "任务名称": record.get("task_name", ""),
                "搜索关键字": record.get("keyword", ""),
                "商品ID": item.get("item_id", ""),
                "商品标题": item.get("title", ""),
                "当前售价": item.get("price", ""),
                "发布时间": item.get("publish_time", ""),
                "发货地区": item.get("shipping_area", ""),
                "浏览量": item.get("view_count", ""),
                "想要人数": item.get("want_count", ""),
                "商品标签": " ".join(str(tag) for tag in tags) if isinstance(tags, list) else tags,
                "卖家在售数": on_sale,
                "卖家已售数": sold,
                "卖家昵称": seller.get("seller_nickname") or item.get("seller_nickname", ""),
                "AI是否推荐": "是" if ai_analysis.get("is_recommended") else "否",
                "分析来源": ai_analysis.get("analysis_source", ""),
                "原因": ai_analysis.get("reason", ""),
                "价格观察次数": price_insight.get("observation_count", ""),
                "价格最低值": price_insight.get("min_price", ""),
                "价格最高值": price_insight.get("max_price", ""),
                "市场均价": price_insight.get("market_avg_price", ""),
                "性价比分数": ai_analysis.get("value_score", price_insight.get("deal_score", "")),
                "性价比标签": ai_analysis.get("value_summary", price_insight.get("deal_label", "")),
                "商品链接": item.get("link", ""),
            }
        )

    return buffer.getvalue()
