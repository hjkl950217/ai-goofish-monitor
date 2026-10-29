import json
from datetime import datetime

from src.config import AI_DEBUG_MODE
from src.utils import safe_get


async def _parse_search_results_json(json_data: dict, source: str) -> list:
    """解析搜索API的JSON数据，返回基础商品信息列表。"""
    page_data = []
    try:
        items = await safe_get(json_data, "data", "resultList", default=[])
        if not items:
            print(f"LOG: ({source}) API响应中未找到商品列表 (resultList)。")
            if AI_DEBUG_MODE:
                print(f"--- [SEARCH DEBUG] RAW JSON RESPONSE from {source} ---")
                print(json.dumps(json_data, ensure_ascii=False, indent=2))
                print("----------------------------------------------------")
            return []

        for item in items:
            main_data = await safe_get(item, "data", "item", "main", "exContent", default={})
            click_params = await safe_get(item, "data", "item", "main", "clickParam", "args", default={})

            title = await safe_get(main_data, "title", default="未知标题")
            price_parts = await safe_get(main_data, "price", default=[])
            price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)]).replace("当前价", "").strip() if isinstance(price_parts, list) else "价格异常"
            # 确保price是字符串类型，避免float类型导致的"in"操作错误
            price = str(price) if not isinstance(price, str) else price
            if "万" in price: price = f"¥{float(price.replace('¥', '').replace('万', '')) * 10000:.0f}"
            area = await safe_get(main_data, "area", default="地区未知")
            seller = await safe_get(main_data, "userNickName", default="匿名卖家")
            raw_link = await safe_get(item, "data", "item", "main", "targetUrl", default="")
            image_url = await safe_get(main_data, "picUrl", default="")
            pub_time_ts = click_params.get("publishTime", "")
            item_id = await safe_get(main_data, "itemId", default="未知ID")
            original_price = await safe_get(main_data, "oriPrice", default="暂无")
            wants_count = await safe_get(click_params, "wantNum", default='NaN')


            tags = []
            if await safe_get(click_params, "tag") == "freeship":
                tags.append("包邮")
            r1_tags = await safe_get(main_data, "fishTags", "r1", "tagList", default=[])
            for tag_item in r1_tags:
                content = await safe_get(tag_item, "data", "content", default="")
                if "验货宝" in content:
                    tags.append("验货宝")

            page_data.append({
                "title": title,
                "price": price,
                "original_price": original_price,
                "want_count": wants_count,
                "tags": tags,
                "shipping_area": area,
                "seller_nickname": seller,
                "link": raw_link.replace("fleamarket://", "https://www.goofish.com/"),
                "publish_time": datetime.fromtimestamp(int(pub_time_ts)/1000).strftime("%Y-%m-%d %H:%M") if pub_time_ts.isdigit() else "未知时间",
                "item_id": item_id
            })
        print(f"LOG: ({source}) 成功解析到 {len(page_data)} 条商品基础信息。")
        return page_data
    except Exception as e:
        print(f"LOG: ({source}) JSON数据处理异常: {str(e)}")
        return []


async def calculate_reputation_from_ratings(ratings_json: list) -> dict:
    """从原始评价API数据列表中，计算作为卖家和买家的好评数与好评率。"""
    seller_total = 0
    seller_positive = 0
    buyer_total = 0
    buyer_positive = 0

    for card in ratings_json:
        # 使用 safe_get 保证安全访问
        data = await safe_get(card, 'cardData', default={})
        role_tag = await safe_get(data, 'rateTagList', 0, 'text', default='')
        rate_type = await safe_get(data, 'rate') # 1=好评, 0=中评, -1=差评

        if "卖家" in role_tag:
            seller_total += 1
            if rate_type == 1:
                seller_positive += 1
        elif "买家" in role_tag:
            buyer_total += 1
            if rate_type == 1:
                buyer_positive += 1

    # 计算比率，并处理除以零的情况
    seller_rate = f"{(seller_positive / seller_total * 100):.2f}%" if seller_total > 0 else "N/A"
    buyer_rate = f"{(buyer_positive / buyer_total * 100):.2f}%" if buyer_total > 0 else "N/A"

    return {
        "seller_good_ratings": f"{seller_positive}/{seller_total}",
        "seller_good_rate": seller_rate,
        "buyer_good_ratings": f"{buyer_positive}/{buyer_total}",
        "buyer_good_rate": buyer_rate
    }


async def _parse_user_items_data(items_json: list) -> list:
    """解析用户主页的商品列表API的JSON数据。"""
    parsed_list = []
    for card in items_json:
        data = card.get('cardData', {})
        status_code = data.get('itemStatus')
        if status_code == 0:
            status_text = "在售"
        elif status_code == 1:
            status_text = "已售"
        else:
            status_text = f"未知状态 ({status_code})"

        parsed_list.append({
            "item_id": data.get('id'),
            "title": data.get('title'),
            "item_price": data.get('priceInfo', {}).get('price'),
            "item_image": data.get('picInfo', {}).get('picUrl'),
            "status": status_text
        })
    return parsed_list


async def parse_user_head_data(head_json: dict) -> dict:
    """解析用户头部API的JSON数据。"""
    data = head_json.get('data', {})
    ylz_tags = await safe_get(data, 'module', 'base', 'ylzTags', default=[])
    seller_credit, buyer_credit = {}, {}
    for tag in ylz_tags:
        if await safe_get(tag, 'attributes', 'role') == 'seller':
            seller_credit = {'level': await safe_get(tag, 'attributes', 'level'), 'text': tag.get('text')}
        elif await safe_get(tag, 'attributes', 'role') == 'buyer':
            buyer_credit = {'level': await safe_get(tag, 'attributes', 'level'), 'text': tag.get('text')}
    return {
        "seller_nickname": await safe_get(data, 'module', 'base', 'displayName'),
        "seller_avatar": await safe_get(data, 'module', 'base', 'avatar', 'avatar'),
        "seller_bio": await safe_get(data, 'module', 'base', 'introduction', default=''),
        "seller_listing_counts": await safe_get(data, 'module', 'tabs', 'item', 'number'),
        "seller_rating_total": await safe_get(data, 'module', 'tabs', 'rate', 'number'),
        "seller_credit_level": seller_credit.get('text', '暂无'),
        "buyer_credit_level": buyer_credit.get('text', '暂无')
    }


async def parse_ratings_data(ratings_json: list) -> list:
    """解析评价列表API的JSON数据。"""
    parsed_list = []
    for card in ratings_json:
        data = await safe_get(card, 'cardData', default={})
        rate_tag = await safe_get(data, 'rateTagList', 0, 'text', default='未知角色')
        rate_type = await safe_get(data, 'rate')
        if rate_type == 1: rate_text = "好评"
        elif rate_type == 0: rate_text = "中评"
        elif rate_type == -1: rate_text = "差评"
        else: rate_text = "未知"
        parsed_list.append({
            "rating_id": data.get('rateId'),
            "rating_content": data.get('feedback'),
            "rating_type": rate_text,
            "rating_role": rate_tag,
            "rating_user": data.get('raterUserNick'),
            "rating_time": data.get('gmtCreate'),
            "rating_images": await safe_get(data, 'pictCdnUrlList', default=[])
        })
    return parsed_list
