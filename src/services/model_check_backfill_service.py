"""历史商品的型号校验。

对已入库的 result_items 逐条跑型号判断，判不过的直接从结果里删掉，
本地图片一并清理。判断结果仍然写 item_model_checks，判过的不会重跑。
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.record_keys import normalize_record
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services import model_check_service

IMAGE_SAVE_DIR = "images"
TASK_IMAGE_DIR_PREFIX = "task_images_"

_lock = asyncio.Lock()
_cancel_event: Optional[asyncio.Event] = None

_status: Dict[str, Any] = {
    "running": False,
    "total": 0,
    "done": 0,
    "matched": 0,
    "removed": 0,
    "failed": 0,
    "message": "",
    "started_at": None,
    "finished_at": None,
    "recent": [],
}


def get_status() -> Dict[str, Any]:
    return dict(_status)


def _push_recent(line: str) -> None:
    recent = _status.setdefault("recent", [])
    recent.append(line)
    if len(recent) > 50:
        del recent[:-50]


# ------------------------------------------------------------------ 取数与删除

def fetch_candidates(result_filename: Optional[str] = None) -> List[sqlite3.Row]:
    """取还没判过的结果条目。判过的（表里有记录）直接跳过。"""
    with sqlite_connection() as conn:
        if result_filename:
            rows = conn.execute(
                "SELECT result_filename, item_id, task_name, keyword, raw_json"
                " FROM result_items WHERE result_filename = ? ORDER BY id",
                (result_filename,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT result_filename, item_id, task_name, keyword, raw_json"
                " FROM result_items ORDER BY id"
            ).fetchall()

    pending = []
    for row in rows:
        item_id = str(row["item_id"] or "").strip()
        if not item_id:
            continue
        task_id = model_check_service.resolve_task_id(str(row["task_name"] or ""))
        if model_check_service.load_check(item_id, task_id) is not None:
            continue
        pending.append(row)
    return pending


def remove_result(result_filename: str, item_id: str, task_name: str) -> None:
    with sqlite_connection() as conn:
        conn.execute(
            "DELETE FROM result_items WHERE result_filename = ? AND item_id = ?",
            (result_filename, item_id),
        )
        conn.commit()
    _remove_images(task_name, item_id)


def _remove_images(task_name: str, item_id: str) -> None:
    """删该商品的所有本地图片。

    图片目录按任务名分，但复查补图时用的是当前任务名，
    历史记录的 task_name 可能对不上，所以扫所有任务目录。
    """
    prefix = f"product_{item_id}_"
    roots = {os.path.join(IMAGE_SAVE_DIR, f"{TASK_IMAGE_DIR_PREFIX}{task_name}")}
    if os.path.isdir(IMAGE_SAVE_DIR):
        for name in os.listdir(IMAGE_SAVE_DIR):
            if name.startswith(TASK_IMAGE_DIR_PREFIX):
                roots.add(os.path.join(IMAGE_SAVE_DIR, name))

    for base in roots:
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if not name.startswith(prefix):
                continue
            try:
                os.remove(os.path.join(base, name))
            except OSError:
                pass


# ------------------------------------------------------------------ 主流程

async def run_check(
    *,
    workers: int = 3,
    result_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """执行历史校验；已在运行时抛 RuntimeError。"""
    global _cancel_event

    if not model_check_service.is_usable():
        raise RuntimeError("型号判断未启用：检查 MODEL_CHECK_ENABLED")
    try:
        model_check_service.load_prompt()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"型号判断提示词不可用: {exc}") from exc

    async with _lock:
        if _status.get("running"):
            raise RuntimeError("已有型号校验任务在运行")
        _cancel_event = asyncio.Event()

    targets = await asyncio.to_thread(fetch_candidates, result_filename)

    _status.update({
        "running": True,
        "total": len(targets),
        "done": 0,
        "matched": 0,
        "removed": 0,
        "failed": 0,
        "message": f"待校验 {len(targets)} 条",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "recent": [],
    })

    if not targets:
        _status.update({
            "running": False,
            "message": "没有需要校验的条目",
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        })
        return get_status()

    semaphore = asyncio.Semaphore(max(1, workers))
    total = len(targets)

    async def check_one(row: sqlite3.Row) -> None:
        async with semaphore:
            item_id = str(row["item_id"] or "").strip()
            record = normalize_record(json.loads(row["raw_json"]))
            item = record.get("item_info", {}) or {}
            try:
                verdict = await model_check_service.check_item(
                    item_id=item_id,
                    task_name=str(row["task_name"] or ""),
                    target=str(row["keyword"] or ""),
                    title=str(item.get("title") or ""),
                    description=str(item.get("description") or ""),
                )
            except Exception as exc:  # noqa: BLE001
                verdict = {"matched": None, "reason": f"异常: {exc}", "source": "error"}

            matched = verdict.get("matched")
            if matched is False:
                try:
                    await asyncio.to_thread(
                        remove_result,
                        str(row["result_filename"]),
                        item_id,
                        str(row["task_name"] or ""),
                    )
                    _status["removed"] += 1
                    flag = "已删除"
                except Exception as exc:  # noqa: BLE001
                    _status["failed"] += 1
                    flag = f"删除失败: {exc}"
            elif matched is True:
                _status["matched"] += 1
                flag = "匹配"
            else:
                _status["failed"] += 1
                flag = "未判出"

            _status["done"] += 1
            _push_recent(f"[{_status['done']}/{total}] {item_id} {flag}")

    try:
        pending = [asyncio.create_task(check_one(row)) for row in targets]
        while pending:
            _, pending = await asyncio.wait(
                pending, timeout=0.5, return_when=asyncio.FIRST_COMPLETED
            )
            if _cancel_event is not None and _cancel_event.is_set():
                for task in pending:
                    task.cancel()
                _push_recent("已取消")
                break
    finally:
        cancelled = _cancel_event is not None and _cancel_event.is_set()
        _status.update({
            "running": False,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "message": (
                f"{'已取消：' if cancelled else '完成：'}匹配 {_status['matched']}，"
                f"删除 {_status['removed']}，未判出 {_status['failed']}"
            ),
        })
        _cancel_event = None

    return get_status()


def cancel_check() -> bool:
    if _cancel_event is not None and _status.get("running"):
        _cancel_event.set()
        return True
    return False
