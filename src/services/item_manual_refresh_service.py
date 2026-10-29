"""手动拉取单个商品的最新详情：标题、描述、价格、图片。

用户对 AI 判定不满意的条目可以手动触发一次，把详情页最新内容写回结果。
不重跑 AI，只更新展示用的字段。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

from src.ai_handler import download_all_images
from src.infrastructure.persistence.record_keys import normalize_record
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.rotation import load_state_files
from src.scraper import (
    _build_context_overrides,
    _build_extra_headers,
    _clean_kwargs,
    _default_context_options,
    _resolve_browser_channel,
    prepare_chromium_launch_args,
)
from src.services.item_refresh_service import parse_detail_price

DETAIL_PATTERN = "mtop.taobao.idle.pc.detail"
DETAIL_TIMEOUT_MS = 25000

# 一次只开一个浏览器，避免连点把容器内存吃满
_lock = asyncio.Lock()


class ItemNotFound(LookupError):
    """结果里没有这个商品。"""


def _state_file() -> Optional[str]:
    override = (os.getenv("MANUAL_REFRESH_STATE_FILE") or "").strip()
    if override and os.path.exists(override):
        return override
    files = load_state_files(os.getenv("ACCOUNT_STATE_DIR", "state"))
    return files[0] if files else None


def _find_row(item_id: str, result_filename: Optional[str]):
    with sqlite_connection() as conn:
        base = (
            "SELECT id, item_id, link, task_name, price, raw_json"
            " FROM result_items WHERE item_id = ?"
        )
        if result_filename:
            return conn.execute(
                base + " AND result_filename = ? ORDER BY id DESC LIMIT 1",
                (item_id, result_filename),
            ).fetchone()
        return conn.execute(
            base + " ORDER BY id DESC LIMIT 1", (item_id,)
        ).fetchone()


async def _capture_detail(item_id: str) -> Dict[str, Any]:
    """打开详情页，拦 mtop 详情接口的响应。"""
    state_file = _state_file()
    if not state_file:
        raise RuntimeError("没有可用的账号登录态文件（state/*.json）")

    try:
        with open(state_file, encoding="utf-8") as fh:
            snapshot = json.load(fh)
    except Exception:  # noqa: BLE001
        snapshot = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel=_resolve_browser_channel(),
            args=prepare_chromium_launch_args(),
        )
        try:
            context_kwargs = _default_context_options()
            storage_state: Any = state_file
            if isinstance(snapshot, dict) and any(
                key in snapshot for key in ("env", "headers", "page", "storage")
            ):
                storage_state = {"cookies": snapshot.get("cookies", [])}
                context_kwargs.update(_build_context_overrides(snapshot))
                extra_headers = _build_extra_headers(snapshot.get("headers"))
                if extra_headers:
                    context_kwargs["extra_http_headers"] = extra_headers
            elif isinstance(snapshot, dict):
                storage_state = snapshot

            context = await browser.new_context(
                storage_state=storage_state,
                **_clean_kwargs(context_kwargs),
            )
            page = await context.new_page()
            captured: Dict[str, Any] = {}

            async def on_response(response):
                if DETAIL_PATTERN in response.url and not captured:
                    try:
                        captured["json"] = await response.json()
                    except Exception:  # noqa: BLE001
                        pass

            page.on("response", on_response)
            try:
                await page.goto(
                    f"https://www.goofish.com/item?id={item_id}",
                    wait_until="domcontentloaded",
                    timeout=DETAIL_TIMEOUT_MS,
                )
                for _ in range(DETAIL_TIMEOUT_MS // 500):
                    if captured:
                        break
                    await asyncio.sleep(0.5)
            finally:
                page.remove_listener("response", on_response)
            return captured.get("json") or {}
        finally:
            await browser.close()


def _parse(detail: Dict[str, Any]) -> Dict[str, Any]:
    item_do = ((detail.get("data") or {}).get("itemDO")) or {}
    if not item_do:
        raise RuntimeError("详情接口没有返回商品数据，可能已下架或登录态失效")
    images = [
        str(img.get("url")).strip()
        for img in (item_do.get("imageInfos") or [])
        if isinstance(img, dict) and img.get("url")
    ]
    return {
        "title": str(item_do.get("title") or "").strip(),
        "description": str(item_do.get("desc") or "").strip(),
        "price": parse_detail_price(item_do),
        "images": images,
        "status": str(item_do.get("itemStatusStr") or "").strip(),
        "want_count": item_do.get("wantCnt"),
        "view_count": item_do.get("browseCnt"),
        "sold_count": item_do.get("soldCnt"),
        "favorite_count": item_do.get("collectCnt"),
    }


def _write_back(row, fields: Dict[str, Any]) -> None:
    record = normalize_record(json.loads(row["raw_json"]))
    info = record.setdefault("item_info", {})
    for key in (
        "title",
        "description",
        "status",
        "want_count",
        "view_count",
        "sold_count",
        "favorite_count",
    ):
        value = fields.get(key)
        if value not in (None, ""):
            info[key] = value
    if fields.get("images"):
        info["images"] = fields["images"]
        info["main_image"] = fields["images"][0]

    now = datetime.now().isoformat(timespec="seconds")
    record["last_checked_at"] = now
    price = fields.get("price")
    old_price = row["price"]
    if price is not None:
        info["price"] = f"¥{price:g}"
    raw = json.dumps(record, ensure_ascii=False)
    with sqlite_connection() as conn:
        conn.execute(
            "UPDATE result_items SET title = ?, price = ?, price_display = ?,"
            " raw_json = ?, last_checked_at = ? WHERE id = ?",
            (
                str(info.get("title") or ""),
                price if price is not None else old_price,
                str(info.get("price") or ""),
                raw,
                now,
                row["id"],
            ),
        )
        conn.commit()


async def refresh_item(
    item_id: str,
    result_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """拉一次详情并写回；返回更新后的完整记录。"""
    item_id = str(item_id or "").strip()
    async with _lock:
        row = _find_row(item_id, result_filename)
        if row is None:
            raise ItemNotFound(item_id)
        detail = await _capture_detail(item_id)
        fields = _parse(detail)
        if fields["images"]:
            await download_all_images(
                item_id, fields["images"], str(row["task_name"] or "default")
            )
        _write_back(row, fields)

    from src.services import item_detail_service

    return item_detail_service.get_item(item_id) or {}
