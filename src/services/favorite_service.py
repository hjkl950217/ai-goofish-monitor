"""
收藏服务：把结果商品同步到闲鱼账号的网页收藏（与手机 App 同源），
并在本地 favorite_items 表持久化收藏状态供前端展示红心。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection

STATE_FILE_ENV = "FAVORITE_STATE_FILE"
ACCOUNT_STATE_DIR_ENV = "ACCOUNT_STATE_DIR"
ROOT_STATE_FILE = "xianyu_state.json"
PAGE_TIMEOUT_MS = 25000
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_lock = asyncio.Lock()


def _candidate_state_file() -> str:
    """取收藏用的登录态：显式配置优先，其次账号池第一个，最后根登录态。"""
    explicit = os.getenv(STATE_FILE_ENV, "").strip().strip('"').strip("'")
    if explicit:
        return explicit
    state_dir = os.getenv(ACCOUNT_STATE_DIR_ENV, "state").strip() or "state"
    if os.path.isdir(state_dir):
        candidates = sorted(f for f in os.listdir(state_dir) if f.endswith(".json"))
        if candidates:
            return os.path.join(state_dir, candidates[0])
    return ROOT_STATE_FILE


def _item_page_url(item_id: str) -> str:
    return f"https://www.goofish.com/item?id={item_id}"


def list_favorites() -> list[dict]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT item_id, link, title, created_at FROM favorite_items ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def _write_local_favorite(item_id: str, link: str | None, title: str | None, favorited: bool) -> None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        if favorited:
            conn.execute(
                "INSERT OR REPLACE INTO favorite_items(item_id, link, title, created_at) VALUES (?, ?, ?, ?)",
                (item_id, link or _item_page_url(item_id), title, datetime.now().isoformat()),
            )
        else:
            conn.execute("DELETE FROM favorite_items WHERE item_id = ?", (item_id,))
        conn.commit()


async def set_favorite(
    item_id: str,
    *,
    action: str,
    link: Optional[str] = None,
    title: Optional[str] = None,
) -> bool:
    """同步闲鱼账号收藏状态，并落本地库。返回最终收藏状态。"""
    desired = action == "add"
    async with _lock:
        final_state = await _sync_site_favorite(item_id, desired)
        _write_local_favorite(item_id, link, title, final_state)
        return final_state


async def _read_button_state(page) -> Optional[str]:
    """返回收藏按钮当前文案：'收藏' / '已收藏' / None。"""
    return await page.evaluate(
        """() => {
            const els = Array.from(document.querySelectorAll('button,[role=button],div,span,a'));
            let best = null, bestLen = Infinity;
            for (const e of els) {
                const t = (e.textContent || '').trim();
                if (t === '收藏' || t === '已收藏') {
                    const depth = e.querySelectorAll('*').length;
                    if (depth < bestLen) { bestLen = depth; best = e; }
                }
            }
            if (!best) return null;
            best.setAttribute('data-favbtn', '1');
            return (best.textContent || '').trim();
        }"""
    )


async def _read_marked_state(page) -> Optional[str]:
    return await page.evaluate(
        """() => {
            const el = document.querySelector('[data-favbtn]');
            if (el) return (el.textContent || '').trim();
            const els = Array.from(document.querySelectorAll('button,[role=button],div,span,a'));
            let best = null, bestLen = Infinity;
            for (const e of els) {
                const t = (e.textContent || '').trim();
                if (t === '收藏' || t === '已收藏') {
                    const depth = e.querySelectorAll('*').length;
                    if (depth < bestLen) { bestLen = depth; best = e; }
                }
            }
            return best ? (best.textContent || '').trim() : null;
        }"""
    )


async def _sync_site_favorite(item_id: str, desired: bool) -> bool:
    state_file = _candidate_state_file()
    if not os.path.exists(state_file):
        raise FileNotFoundError(f"收藏服务需要登录态文件: {state_file}")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chromium",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            with open(state_file, encoding="utf-8") as fh:
                snapshot = json.load(fh)
            storage = (
                {"cookies": snapshot["cookies"]}
                if isinstance(snapshot, dict) and "cookies" in snapshot
                else state_file
            )
            context = await browser.new_context(storage_state=storage, user_agent=UA)
            page = await context.new_page()

            try:
                await page.goto(
                    _item_page_url(item_id),
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT_MS,
                )
                current = None
                for _ in range(PAGE_TIMEOUT_MS // 500):
                    current = await _read_button_state(page)
                    if current is not None:
                        break
                    await asyncio.sleep(0.5)

                if current is None:
                    raise RuntimeError(f"页面未找到收藏按钮 (item {item_id})")

                already = current == "已收藏"
                if already == desired:
                    return already

                target = page.get_by_text("已收藏" if already else "收藏", exact=True).first
                await target.click()
                await page.wait_for_timeout(2500)
                for _ in range(12):
                    after = await _read_marked_state(page)
                    if after in ("收藏", "已收藏") and after != current:
                        return after == "已收藏"
                    await asyncio.sleep(0.5)
                after = await _read_marked_state(page)
                return after == "已收藏"
            finally:
                await context.close()
        finally:
            await browser.close()