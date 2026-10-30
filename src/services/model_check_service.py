"""型号判断：判断商品是不是任务搜索的目标型号。

在「抓详情 → AI 分析」之间插入。判据是任务的搜索关键字。
结果按 (item_id, task_id) 落到 item_model_checks 表，同一商品同一任务只判一次。
判断不了（AI 报错、返回 null）一律放行，不能让型号环节变成丢数据的单点。
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.infrastructure.config.settings import AISettings
from src.infrastructure.external.ai_client import AIClient
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.ai_response_parser import parse_ai_response_json
from src.services.prompt_defaults import ensure_default_prompts

PROMPT_FILE = Path("prompts") / "model_check_prompt.txt"

_client_state: dict = {"key": None, "client": None}


# ------------------------------------------------------------------ 配置

def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _build_settings() -> AISettings:
    """MODEL_CHECK_* 留空就回退到主 AI 配置。"""
    settings = AISettings()
    settings.base_url = _env("MODEL_CHECK_BASE_URL") or settings.base_url
    settings.api_key = _env("MODEL_CHECK_API_KEY") or settings.api_key
    settings.model_name = _env("MODEL_CHECK_MODEL_NAME") or settings.model_name
    settings.proxy_url = _env("MODEL_CHECK_PROXY_URL") or settings.proxy_url
    return settings


def is_enabled() -> bool:
    value = _env("MODEL_CHECK_ENABLED") or "true"
    return value.lower() not in {"0", "false", "no", "off"}


def is_usable() -> bool:
    """开关打开就启用；提示词缺文件会从内置副本补出来。"""
    return is_enabled()


def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        ensure_default_prompts()
    return PROMPT_FILE.read_text(encoding="utf-8")


def _get_client() -> AIClient:
    """配置变化时重建 client，改完设置不用重启容器。"""
    settings = _build_settings()
    key = (settings.base_url, settings.api_key, settings.model_name, settings.proxy_url)
    if _client_state["key"] != key or _client_state["client"] is None:
        _client_state["client"] = AIClient(settings)
        _client_state["key"] = key
    return _client_state["client"]


# ------------------------------------------------------------------ 预筛

def prefilter_passes(text: str) -> bool:
    """本地正则预筛，只做放行不做拒绝。

    命中说明文本里明确出现了目标写法，直接放行省一次 AI 调用；
    没命中不代表不是，继续交给模型判断。正则为空则完全跳过预筛。
    """
    pattern = _env("MODEL_CHECK_PREFILTER_REGEX")
    if not pattern:
        return False
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return False
    return compiled.search(text) is not None


# ------------------------------------------------------------------ 落表

def resolve_task_id(task_name: str) -> int:
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE task_name = ?", (task_name,)
        ).fetchone()
    return int(row["id"]) if row else -1


def load_check(item_id: str, task_id: int) -> Optional[dict]:
    """有记录就返回，没有返回 None。matched 可能是 None（判断不了）。"""
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT matched, reason FROM item_model_checks"
            " WHERE item_id = ? AND task_id = ?",
            (item_id, task_id),
        ).fetchone()
    if row is None:
        return None
    matched = None if row["matched"] is None else bool(row["matched"])
    return {"matched": matched, "reason": row["reason"] or ""}


def save_check(item_id: str, task_id: int, matched: Optional[bool], reason: str,
               checked_at: str) -> None:
    stored = None if matched is None else (1 if matched else 0)
    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO item_model_checks
                (item_id, task_id, matched, reason, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(item_id), int(task_id), stored, reason, checked_at),
        )
        conn.commit()


# ------------------------------------------------------------------ 主流程

async def check_item(
    *,
    item_id: str,
    task_name: str,
    target: str,
    title: str,
    description: str,
) -> dict:
    """判断单个商品。

    返回 {"matched": True/False/None, "reason": str, "source": str}。
    matched 为 None 表示判不出，调用方用 is_accepted 决定去留。命中缓存时不重复调 AI。
    """
    if not is_usable():
        return {"matched": None, "reason": "型号判断未启用", "source": "skipped"}

    item_id = str(item_id or "").strip()
    if not item_id:
        return {"matched": None, "reason": "缺少商品 ID", "source": "skipped"}

    task_id = resolve_task_id(task_name)
    cached = load_check(item_id, task_id)
    if cached is not None:
        return {**cached, "source": "cache"}

    text = f"{title}\n{description}".strip()
    if prefilter_passes(text):
        save_check(item_id, task_id, True, "本地预筛命中", datetime.now().isoformat(timespec="seconds"))
        return {"matched": True, "reason": "本地预筛命中", "source": "prefilter"}

    prompt = load_prompt().replace("{{TARGET}}", target or "")
    content = f"{prompt}\n\n商品标题：{title or '无'}\n商品描述：{description or '无'}"
    # 单次网络抖动不该直接判成不通过，失败后重试一次
    for attempt in range(2):
        try:
            raw = await _get_client().complete(
                [{"role": "user", "content": content}],
                temperature=0.05,
                max_output_tokens=300,
            )
            parsed = parse_ai_response_json(raw)
            matched = parsed.get("matched")
            if not isinstance(matched, bool):
                matched = None
            reason = str(parsed.get("reason") or "").strip()[:500]
            source = "ai"
            break
        except Exception as exc:  # noqa: BLE001
            matched = None
            reason = f"型号判断失败: {exc}"[:500]
            source = "error"
            print(f"   [型号] 判断调用失败({attempt + 1}/2)，按不通过处理: {exc}")
            if attempt == 0:
                await asyncio.sleep(1)

    # 调用失败不算判断结果，不写缓存，下次还能重判
    if source != "error":
        save_check(item_id, task_id, matched, reason, datetime.now().isoformat(timespec="seconds"))
    return {"matched": matched, "reason": reason, "source": source}


def is_accepted(verdict: Optional[dict]) -> bool:
    """型号校验是否放行。只有明确匹配才放行。

    判不出、调用失败、以及"跳过校验"都不放行：跳过不等于型号被认可，
    放行会让不符合型号的商品静默入库。任务关掉型号判断时调用方不会走到这里。
    """
    if verdict is None:
        return False
    return verdict.get("matched") is True
