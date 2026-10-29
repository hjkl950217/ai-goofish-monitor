"""商品详情服务：按商品 ID 提供完整记录与已下载图片。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.record_keys import normalize_record
from src.infrastructure.persistence.sqlite_connection import sqlite_connection

IMAGE_SAVE_DIR = "images"
TASK_IMAGE_DIR_PREFIX = "task_images_"

def _is_safe_name(name: str) -> bool:
    """仅阻断路径穿越；阿里云图片名含 ~ ! 等字符，不能用字符白名单。"""
    if not name or name in (".", ".."):
        return False
    if "/" in name or "\\" in name or chr(0) in name:
        return False
    if name.startswith("."):
        return False
    return True


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    """返回单条商品的完整记录（含 AI 结论与价格参考）。"""
    from src.services.result_file_service import enrich_records_with_price_insight

    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT id, result_filename, item_id, raw_json, is_recommended, "
            "analysis_source, status, crawl_time, price, initial_price, last_checked_at "
            "FROM result_items WHERE item_id = ? ORDER BY id LIMIT 1",
            (str(item_id),),
        ).fetchone()
    if not row:
        return None

    record = normalize_record(json.loads(row["raw_json"]))
    record["_meta"] = {
        "id": row["id"],
        "result_filename": row["result_filename"],
        "item_id": row["item_id"],
        "is_recommended": bool(row["is_recommended"]),
        "analysis_source": row["analysis_source"],
        "status": row["status"],
        "crawl_time": row["crawl_time"],
        "price": row["price"],
        "initial_price": row["initial_price"],
        "last_checked_at": row["last_checked_at"],
    }
    enriched = enrich_records_with_price_insight([record], row["result_filename"])
    return enriched[0] if enriched else record


def list_item_images(item_id: str) -> List[Dict[str, Any]]:
    """列出该商品已下载到本地的图片（按图片序号排序）。"""
    item_id = str(item_id)
    root = IMAGE_SAVE_DIR
    images: List[Dict[str, Any]] = []
    if not os.path.isdir(root):
        return images

    for task_dir in sorted(os.listdir(root)):
        if not task_dir.startswith(TASK_IMAGE_DIR_PREFIX):
            continue
        dir_path = os.path.join(root, task_dir)
        if not os.path.isdir(dir_path):
            continue
        for name in os.listdir(dir_path):
            # product_<item_id>_<序号>_<原始文件名>
            if not name.startswith(f"product_{item_id}_"):
                continue
            if not _is_safe_name(name):
                continue
            full = os.path.join(dir_path, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            index = _extract_index(name, item_id)
            images.append({
                "name": name,
                "task": task_dir[len(TASK_IMAGE_DIR_PREFIX):],
                "index": index,
                "size": size,
                "url": f"/api/items/{item_id}/images/{name}",
            })

    images.sort(key=lambda x: (x["index"] if x["index"] is not None else 9999, x["name"]))
    return images


def _extract_index(name: str, item_id: str) -> Optional[int]:
    rest = name[len(f"product_{item_id}_"):]
    head = rest.split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def resolve_image_path(item_id: str, name: str) -> Optional[str]:
    """在缓存目录中定位图片文件，阻断路径穿越。"""
    item_id = str(item_id)
    if not _is_safe_name(name or ""):
        return None
    if not name.startswith(f"product_{item_id}_"):
        return None

    root = os.path.abspath(IMAGE_SAVE_DIR)
    if not os.path.isdir(root):
        return None
    for task_dir in sorted(os.listdir(root)):
        if not task_dir.startswith(TASK_IMAGE_DIR_PREFIX):
            continue
        candidate = os.path.abspath(
            os.path.join(IMAGE_SAVE_DIR, task_dir, name)
        )
        if not candidate.startswith(root + os.sep):
            continue
        if os.path.isfile(candidate):
            return candidate
    return None