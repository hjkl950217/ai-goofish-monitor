"""结果卡片视图：裁掉列表里用不到的重字段。

一条结果 26KB 左右，大头是 seller_items（9KB）、seller_ratings（6.8KB）、
criteria_analysis（4.3KB）和 description/images——卡片一个都不显示。
裁完约 3.5KB，100 条从 2.6MB 降到 350KB。
"""
from __future__ import annotations

from typing import Any, Dict

from src.services.image_proxy_service import DEFAULT_WIDTH, proxy_url

_HEAVY_ITEM_FIELDS = ("description", "images")
_HEAVY_SELLER_FIELDS = ("seller_items", "seller_ratings", "seller_bio", "seller_avatar")
_HEAVY_AI_FIELDS = ("criteria_analysis",)
_DROP_TOP_LEVEL = ("price_reference",)


def _listing_counts(seller: Dict[str, Any]) -> tuple[int, int]:
    on_sale = sold = 0
    for entry in seller.get("seller_items") or []:
        status = entry.get("status") if isinstance(entry, dict) else None
        if status == "在售":
            on_sale += 1
        elif status == "已售":
            sold += 1
    return on_sale, sold


def compact_card_record(record: Dict[str, Any], image_width: int = DEFAULT_WIDTH) -> Dict[str, Any]:
    """返回只剩卡片需要的字段的副本，原记录不动。"""
    out = {key: value for key, value in record.items() if key not in _DROP_TOP_LEVEL}

    item = dict(record.get("item_info") or {})
    for key in _HEAVY_ITEM_FIELDS:
        item.pop(key, None)
    # 图片换成后端缩略图地址，前端照旧 <img src>
    if item.get("main_image"):
        item["main_image"] = proxy_url(item["main_image"], image_width)
    out["item_info"] = item

    seller = dict(record.get("seller_info") or {})
    if seller.get("seller_items"):
        # 卡片只用「在售 X / 已售 Y」，明细整段丢掉，计数留成两个小字段
        seller["on_sale_count"], seller["sold_count"] = _listing_counts(seller)
    for key in _HEAVY_SELLER_FIELDS:
        seller.pop(key, None)
    out["seller_info"] = seller

    if isinstance(record.get("ai_analysis"), dict):
        ai = dict(record["ai_analysis"])
        for key in _HEAVY_AI_FIELDS:
            ai.pop(key, None)
        out["ai_analysis"] = ai

    return out
