"""结果记录的中文键到英文键映射。

新数据只写英文键。旧数据（raw_json 里仍是中文键）在读取时统一归一化，
保证升级后老任务的结果照样能显示、能筛选。
"""
from __future__ import annotations

from typing import Any

LEGACY_KEY_MAP: dict[str, str] = {
    # 顶层
    "爬取时间": "crawl_time",
    "搜索关键字": "keyword",
    "任务名称": "task_name",
    "任务名": "task_name",
    "商品信息": "item_info",
    "卖家信息": "seller_info",
    "价格参考": "price_reference",
    "复查时间": "last_checked_at",
    # 商品
    "商品ID": "item_id",
    "商品标题": "title",
    "当前售价": "price",
    "商品原价": "original_price",
    "“想要”人数": "want_count",
    "商品标签": "tags",
    "发货地区": "shipping_area",
    "卖家昵称": "seller_nickname",
    "商品链接": "link",
    "发布时间": "publish_time",
    "商品图片列表": "images",
    "商品主图链接": "main_image",
    "商品描述": "description",
    "浏览量": "view_count",
    "商品已售数": "sold_count",
    "商品收藏数": "favorite_count",
    "商品状态": "status",
    # 卖家
    "卖家头像链接": "seller_avatar",
    "卖家个性签名": "seller_bio",
    "卖家在售/已售商品数": "seller_listing_counts",
    "卖家收到的评价总数": "seller_rating_total",
    "卖家信用等级": "seller_credit_level",
    "买家信用等级": "buyer_credit_level",
    "卖家芝麻信用": "seller_zhima_credit",
    "卖家注册时长": "seller_registered_years",
    "作为卖家的好评数": "seller_good_ratings",
    "作为卖家的好评率": "seller_good_rate",
    "作为买家的好评数": "buyer_good_ratings",
    "作为买家的好评率": "buyer_good_rate",
    "卖家发布的商品列表": "seller_items",
    "卖家收到的评价列表": "seller_ratings",
    "卖家累计已售数": "seller_total_sold",
    # 卖家主页里的商品条目
    "商品价格": "item_price",
    "商品主图": "item_image",
    # 评价
    "评价ID": "rating_id",
    "评价内容": "rating_content",
    "评价类型": "rating_type",
    "评价来源角色": "rating_role",
    "评价者昵称": "rating_user",
    "评价时间": "rating_time",
    "评价图片": "rating_images",
}


def normalize_keys(value: Any) -> Any:
    """递归把中文键换成英文，英文键原样保留。"""
    if isinstance(value, dict):
        return {LEGACY_KEY_MAP.get(key, key): normalize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_keys(item) for item in value]
    return value


def normalize_record(record: dict) -> dict:
    return normalize_keys(record)
