"""
AI 响应解析工具
"""
import json
from typing import Any


class EmptyAIResponseError(ValueError):
    """AI 返回了空内容。"""


def validate_analysis_result(result: dict) -> None:
    """检查分析结构，以及明确硬条件和最终推荐是否自相矛盾。"""
    required = {"prompt_version", "is_recommended", "reason", "risk_tags", "criteria_analysis"}
    if not isinstance(result, dict) or not required.issubset(result):
        raise ValueError("分析结果缺少必需字段")
    criteria = result["criteria_analysis"]
    if not isinstance(criteria, dict) or not criteria or "seller_type" not in criteria:
        raise ValueError("criteria_analysis必须为非空对象且包含seller_type")
    if not isinstance(result["is_recommended"], bool):
        raise ValueError("is_recommended必须为布尔值")
    if not isinstance(result["reason"], str) or not isinstance(result["prompt_version"], str):
        raise ValueError("reason和prompt_version必须为字符串")
    if not isinstance(result["risk_tags"], list) or not all(isinstance(tag, str) for tag in result["risk_tags"]):
        raise ValueError("risk_tags必须为字符串数组")

    hard = result.get("hard_requirements", {})
    if not isinstance(hard, dict):
        raise ValueError("hard_requirements必须为对象")
    for name, entry in hard.items():
        if not isinstance(entry, dict) or entry.get("status") not in {"PASS", "FAIL", "UNKNOWN", "NEEDS_MANUAL_CHECK"}:
            raise ValueError(f"硬条件{name}缺少有效状态")
        if result["is_recommended"] and entry["status"] != "PASS":
            raise ValueError(f"硬条件{name}未通过，不能推荐")

    # 兼容旧标准：model_chip一直表示目标型号，不把电池、成色等参考项一律否决。
    model = criteria.get("model_chip")
    if result["is_recommended"] and isinstance(model, dict) and model.get("status") in {"FAIL", "UNKNOWN", "NEEDS_MANUAL_CHECK"}:
        raise ValueError("目标型号未通过，不能推荐")


def extract_ai_response_content(response: Any) -> str:
    """从不同形态的 AI 响应中提取文本内容。"""
    if response is None:
        raise EmptyAIResponseError("AI响应对象为空。")

    if isinstance(response, (bytes, bytearray)):
        text = response.decode("utf-8", errors="replace")
        return _normalize_text_content(text)

    if isinstance(response, str):
        return _normalize_text_content(response)

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return _normalize_text_content(output_text)

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is None:
            raise EmptyAIResponseError("AI响应缺少 message。")
        content = getattr(message, "content", None)
        
        # 智谱等 OpenAI 兼容网关在某些模式下会把输出放在 reasoning_content 而非 content
        try:
            return _normalize_text_content(_coerce_content_parts(content))
        except EmptyAIResponseError:
            reasoning_content = getattr(message, "reasoning_content", None)
            if reasoning_content:
                return _normalize_text_content(_coerce_content_parts(reasoning_content))
            raise

    raise ValueError(f"无法识别的AI响应类型: {type(response).__name__}")


def parse_ai_response_json(content: str) -> dict:
    """解析 AI 文本响应中的 JSON。"""
    cleaned = _strip_code_fences(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return _extract_first_json_value(cleaned, exc)


def _coerce_content_parts(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8", errors="replace")
    if not isinstance(content, list):
        raise ValueError(f"AI响应内容类型不受支持: {type(content).__name__}")

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
            continue
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _normalize_text_content(content: str) -> str:
    text = str(content).strip()
    if not text:
        raise EmptyAIResponseError("AI响应内容为空。")
    return text


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_first_json_value(
    content: str,
    fallback_error: json.JSONDecodeError,
):
    decoder = json.JSONDecoder()
    last_error: json.JSONDecodeError | None = None

    for start_index, char in enumerate(content):
        if char not in "{[":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[start_index:])
            return parsed
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise fallback_error
