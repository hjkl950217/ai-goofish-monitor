"""
AI 请求消息构造辅助函数
"""
import json
from typing import Dict, List, Union


def serialize_analysis_data(product_data: dict) -> str:
    """只发送本次分析的事实，不让旧结论和未核实的价格参考影响重判。"""
    payload = {key: value for key, value in product_data.items() if key != "ai_analysis"}
    for key in ("price_reference", "price_insight", "价格参考"):
        reference = payload.get(key)
        # 重分析时价格参考可能已过期，不能沿用旧结论生成时的估价。
        if reference is not None and (
            "ai_analysis" in product_data
            or not isinstance(reference, dict)
            or reference.get("comparison_verified") is not True
        ):
            payload.pop(key)
            payload["price_reference_status"] = "缺少当前已核实的可比样本，不能据搜索均价判定高低价"
    return json.dumps(payload, ensure_ascii=False, indent=2)


TEXT_ONLY_ANALYSIS_NOTE = (
    "补充说明：本次未提供商品图片，请仅根据商品文字字段和卖家信息判断，不要推断图片内容。"
)


def build_analysis_text_prompt(
    product_json: str,
    prompt_text: str,
    *,
    include_images: bool,
) -> str:
    note = "" if include_images else f"\n{TEXT_ONLY_ANALYSIS_NOTE}\n"
    value_note = (
        "\n如果商品 JSON 中包含“价格参考”或 price_insight，请结合价格位置、历史走势、"
        "配置、成色、附件、卖家信息综合判断性价比。"
        "两者同时存在时以 price_insight 为准：它是当前最新值，“价格参考”只是抓取时点的快照。"
        "你必须输出 value_score（0-100 的整数）和 value_summary（简短的性价比结论）两个字段，"
        "不允许省略；同时必须保留原有 is_recommended/reason 等字段。\n"
    )
    return f"""请基于你的专业知识和我的要求，分析以下完整的商品JSON数据：

```json
{product_json}
```

    {prompt_text}
    {value_note}
    {note}"""


def build_user_message_content(
    text_prompt: str,
    image_data_urls: List[str],
) -> Union[str, List[Dict[str, object]]]:
    if not image_data_urls:
        return text_prompt

    user_content: List[Dict[str, object]] = [
        {"type": "image_url", "image_url": {"url": url}}
        for url in image_data_urls
    ]
    user_content.append({"type": "text", "text": text_prompt})
    return user_content
