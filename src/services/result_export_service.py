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
    items = seller.get("卖家发布的商品列表") or []
    on_sale = sum(1 for entry in items if isinstance(entry, dict) and entry.get("商品状态") == "在售")
    sold = sum(1 for entry in items if isinstance(entry, dict) and entry.get("商品状态") == "已售")
    return on_sale, sold


def build_results_csv(records: list[dict]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_HEADERS)
    writer.writeheader()

    for record in records:
        item = record.get("商品信息", {}) or {}
        seller = record.get("卖家信息", {}) or {}
        ai_analysis = record.get("ai_analysis", {}) or {}
        price_insight = record.get("price_insight", {}) or {}
        on_sale, sold = _listing_counts(seller)
        tags = item.get("商品标签") or []
        writer.writerow(
            {
                "任务名称": record.get("任务名称", ""),
                "搜索关键字": record.get("搜索关键字", ""),
                "商品ID": item.get("商品ID", ""),
                "商品标题": item.get("商品标题", ""),
                "当前售价": item.get("当前售价", ""),
                "发布时间": item.get("发布时间", ""),
                "发货地区": item.get("发货地区", ""),
                "浏览量": item.get("浏览量", ""),
                "想要人数": item.get("“想要”人数", ""),
                "商品标签": " ".join(str(tag) for tag in tags) if isinstance(tags, list) else tags,
                "卖家在售数": on_sale,
                "卖家已售数": sold,
                "卖家昵称": seller.get("卖家昵称") or item.get("卖家昵称", ""),
                "AI是否推荐": "是" if ai_analysis.get("is_recommended") else "否",
                "分析来源": ai_analysis.get("analysis_source", ""),
                "原因": ai_analysis.get("reason", ""),
                "价格观察次数": price_insight.get("observation_count", ""),
                "价格最低值": price_insight.get("min_price", ""),
                "价格最高值": price_insight.get("max_price", ""),
                "市场均价": price_insight.get("market_avg_price", ""),
                "性价比分数": ai_analysis.get("value_score", price_insight.get("deal_score", "")),
                "性价比标签": ai_analysis.get("value_summary", price_insight.get("deal_label", "")),
                "商品链接": item.get("商品链接", ""),
            }
        )

    return buffer.getvalue()
