"""商品复查：定期回访详情页，记录价格/描述变化，标记下架。

每轮任务结束后从 active 商品里随机抽 5-20 个回访。价格或描述变了才需要
重新跑 AI 分析；没变的只更新复查时间，避免无谓的模型调用。
price 存最新价，initial_price 存加入时的价格。
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.price_history_service import parse_price_value

REFRESH_MIN_PER_RUN = 5
REFRESH_MAX_PER_RUN = 20

# itemDO.itemStatusStr 命中这些词才判定商品不在售。
# 用白名单式黑名单：闲鱼新增状态文案时宁可漏判，也不要把在售商品标成下架。
OFFLINE_STATUS_TEXTS = ("已下架", "已售出", "已卖出", "已删除", "已失效")


def build_content_fingerprint(price_display: str, description: str) -> str:
    payload = f"{(price_display or '').strip()}\n{(description or '').strip()}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def is_offline_status(status_text: str) -> bool:
    text = (status_text or "").strip()
    return any(keyword in text for keyword in OFFLINE_STATUS_TEXTS)


def pick_refresh_targets(
    result_filename: str,
    per_run: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """挑出本轮要回访的商品：最久没查的 2 倍池子里随机抽。"""
    limit = (
        per_run
        if per_run is not None
        else random.randint(REFRESH_MIN_PER_RUN, REFRESH_MAX_PER_RUN)
    )
    if limit <= 0:
        return []

    with sqlite_connection() as conn:
        rows = conn.execute(
            """
            SELECT item_id, link, price, price_display, content_hash,
                   last_checked_at, is_recommended
            FROM result_items
            WHERE result_filename = ?
              AND status = 'active'
              AND item_id IS NOT NULL
              AND item_id <> ''
            ORDER BY COALESCE(last_checked_at, '') ASC
            LIMIT ?
            """,
            (result_filename, limit * 2),
        ).fetchall()

    candidates = [dict(row) for row in rows]
    random.shuffle(candidates)
    return candidates[:limit]


def record_refresh(
    *,
    result_filename: str,
    item_id: str,
    price: Optional[float] = None,
    description: Optional[str] = None,
    image_urls: Optional[List[str]] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """落库一次回访结果。

    返回 {"changed": bool, "images_changed": bool, "offline": bool, "record": dict | None}。
    changed 表示价格或描述变了，调用方应重新跑 AI 分析；
    images_changed 表示图片张数变了，调用方应重新下载图片。
    """
    now = datetime.now().isoformat()

    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT raw_json, content_hash, price FROM result_items"
            " WHERE result_filename = ? AND item_id = ?",
            (result_filename, item_id),
        ).fetchone()
        if row is None:
            return {
                "changed": False,
                "images_changed": False,
                "offline": False,
                "record": None,
            }

        if offline:
            conn.execute(
                "UPDATE result_items SET status = 'expired', last_checked_at = ?"
                " WHERE result_filename = ? AND item_id = ?",
                (now, result_filename, item_id),
            )
            conn.commit()
            return {
                "changed": False,
                "images_changed": False,
                "offline": True,
                "record": None,
            }

        record = json.loads(row["raw_json"])
        info = record.setdefault("商品信息", {})
        old_price = float(row["price"]) if row["price"] is not None else None
        new_price = price if price is not None else old_price
        price_display = _format_price(new_price) or str(info.get("当前售价") or "")
        desc = (description or "").strip() or str(info.get("商品描述") or "")
        fingerprint = build_content_fingerprint(price_display, desc)
        stored = str(row["content_hash"] or "")

        # 老数据没有指纹基线：首次只补基线，变化按价格判断
        changed = (
            stored != fingerprint
            if stored
            else (new_price is not None and old_price is not None and new_price != old_price)
        )

        # 图片很少变，只比张数，避免每轮都重新下载
        new_images = [str(url).strip() for url in (image_urls or []) if str(url).strip()]
        old_images = info.get("商品图片列表") or []
        images_changed = bool(new_images) and len(new_images) != len(old_images)

        if not changed and not images_changed:
            conn.execute(
                "UPDATE result_items SET content_hash = ?, last_checked_at = ?"
                " WHERE result_filename = ? AND item_id = ?",
                (fingerprint, now, result_filename, item_id),
            )
            conn.commit()
            return {
                "changed": False,
                "images_changed": False,
                "offline": False,
                "record": None,
            }

        info["当前售价"] = price_display
        if desc:
            info["商品描述"] = desc
        if images_changed:
            info["商品图片列表"] = new_images
            info["商品主图链接"] = new_images[0]
        record["复查时间"] = now
        conn.execute(
            """
            UPDATE result_items
            SET price = ?, price_display = ?, content_hash = ?,
                last_checked_at = ?, raw_json = ?
            WHERE result_filename = ? AND item_id = ?
            """,
            (
                new_price,
                price_display,
                fingerprint,
                now,
                json.dumps(record, ensure_ascii=False),
                result_filename,
                item_id,
            ),
        )
        conn.commit()

    return {
        "changed": changed,
        "images_changed": images_changed,
        "offline": False,
        "record": record if changed else None,
    }


def _format_price(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"¥{value:g}"


def parse_detail_price(item_do: Dict[str, Any]) -> Optional[float]:
    """详情接口的价格字段是 soldPrice，字符串或数字都可能。"""
    return parse_price_value(item_do.get("soldPrice"))
