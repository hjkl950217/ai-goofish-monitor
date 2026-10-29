"""商品重新 AI 分析服务。

与 scripts/backfill_details.py 共用同一套状态与落库逻辑，
既可由命令行调用，也可由前端按钮触发（后台任务 + 状态查询）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.analysis_prompt_builder import build_analysis_prompt

STATE_PATH = "data/backfill_state.json"

SCOPE_PENDING = "pending"   # 仅未分析过的
SCOPE_ALL = "all"           # 全部重跑
SCOPE_SELECTED = "selected"  # 指定 item_id 列表

_lock = asyncio.Lock()
_cancel_event: Optional[asyncio.Event] = None

_status: Dict[str, Any] = {
    "running": False,
    "scope": "",
    "total": 0,
    "done": 0,
    "ok": 0,
    "failed": 0,
    "message": "",
    "started_at": None,
    "finished_at": None,
    "recent": [],
}


class ReanalyzeBusyError(RuntimeError):
    """已有重新分析任务在运行。"""


# --------------------------------------------------------------- 状态与数据库

def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"analyzed": {}, "dead": {}, "uncertain": {}, "failed_analyze": []}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"analyzed": {}, "dead": {}, "uncertain": {}, "failed_analyze": []}
    state.setdefault("analyzed", {})
    state.setdefault("dead", {})
    state.setdefault("uncertain", {})
    state.setdefault("failed_analyze", [])
    return state


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def fetch_rows(result_filename: Optional[str] = None) -> List[sqlite3.Row]:
    with sqlite_connection() as conn:
        if result_filename:
            return list(conn.execute(
                "SELECT id, item_id, raw_json FROM result_items "
                "WHERE result_filename = ? ORDER BY id",
                (result_filename,),
            ))
        return list(conn.execute(
            "SELECT id, item_id, raw_json FROM result_items ORDER BY id"
        ))


def build_prompt(task_name: Optional[str] = None):
    """按任务配置组装 prompt：base_prompt + criteria 模板。"""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    with sqlite_connection() as conn:
        if task_name:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_name = ?", (task_name,)
            ).fetchone()
        else:
            # 优先使用启用的任务；若全部停用则退回最近一个（重新分析不依赖任务运行状态）
            row = conn.execute(
                "SELECT * FROM tasks ORDER BY enabled DESC, id ASC LIMIT 1"
            ).fetchone()
    if not row:
        raise RuntimeError("未找到可用任务（检查任务是否启用）")
    prompt = build_analysis_prompt(row, root=repo_root)
    if len(prompt) < 100 or "{{CRITERIA_SECTION}}" in prompt:
        raise RuntimeError(f"prompt 组装异常（长度 {len(prompt)}）")
    return str(row["task_name"]), prompt


# --------------------------------------------------------------- 进度

def get_status() -> Dict[str, Any]:
    return dict(_status)


def _push_recent(line: str) -> None:
    recent = _status.setdefault("recent", [])
    recent.append(line)
    if len(recent) > 50:
        del recent[:-50]


# --------------------------------------------------------------- 主流程

def _select_targets(state: dict, scope: str, only_ids: Optional[List[str]],
                    result_filename: Optional[str]) -> List[sqlite3.Row]:
    rows = fetch_rows(result_filename)
    dead_ids = set(state.get("dead", {}))
    analyzed = state.get("analyzed", {})

    if scope == SCOPE_ALL:
        candidates = [r for r in rows if str(r["item_id"]) not in dead_ids]
    elif scope == SCOPE_SELECTED and only_ids:
        wanted = {str(i) for i in only_ids}
        candidates = [r for r in rows if str(r["item_id"]) in wanted]
    else:
        candidates = [
            r for r in rows
            if str(r["item_id"]) not in analyzed and str(r["item_id"]) not in dead_ids
        ]
    return candidates


async def run_analyze(
    *,
    scope: str = SCOPE_PENDING,
    limit: Optional[int] = None,
    workers: int = 3,
    only_ids: Optional[List[str]] = None,
    result_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """执行重新分析；已在运行时抛 ReanalyzeBusyError。"""
    global _cancel_event

    async with _lock:
        if _status.get("running"):
            raise ReanalyzeBusyError("已有重新分析任务在运行")
        _cancel_event = asyncio.Event()

    from src.ai_handler import cleanup_task_images, download_all_images, get_ai_analysis

    state = load_state()
    task_name, prompt = build_prompt(None)

    targets = _select_targets(state, scope, only_ids, result_filename)
    if limit:
        targets = targets[:limit]

    _status.update({
        "running": True,
        "scope": scope,
        "total": len(targets),
        "done": 0,
        "ok": 0,
        "failed": 0,
        "message": f"待重算 {len(targets)} 条（worker={workers}）",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "recent": [],
    })
    _push_recent(f"任务={task_name}，prompt 长度={len(prompt)}")

    if not targets:
        _status.update({
            "running": False,
            "message": "没有需要分析的条目",
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        })
        return get_status()

    semaphore = asyncio.Semaphore(max(1, workers))
    total = len(targets)
    save_state(state)  # 立即落盘，避免 UI 误显示为"进行中"

    async def analyze_one(row: sqlite3.Row) -> None:
        async with semaphore:
            item_id = str(row["item_id"])
            record = json.loads(row["raw_json"])
            item = record.get("商品信息", {}) or {}
            urls = item.get("商品图片列表") or (
                [item["商品主图链接"]] if item.get("商品主图链接") else []
            )
            image_paths: List[str] = []
            result = None
            try:
                if urls:
                    image_paths = await download_all_images(item_id, urls, task_name="backfill")
                result = await get_ai_analysis(record, image_paths, prompt)
            except Exception as exc:  # noqa: BLE001
                _push_recent(f"[x] {item_id} 分析异常: {exc}")

            if result:
                result.setdefault("analysis_source", "ai")
                result.setdefault("keyword_hit_count", 0)
                result["backfilled_at"] = datetime.now().isoformat()
                record["ai_analysis"] = result
                with sqlite_connection() as conn:
                    conn.execute(
                        """
                        UPDATE result_items
                        SET raw_json = ?, is_recommended = ?, analysis_source = ?,
                            keyword_hit_count = ?, status = 'active'
                        WHERE id = ?
                        """,
                        (
                            json.dumps(record, ensure_ascii=False),
                            1 if result.get("is_recommended") else 0,
                            result.get("analysis_source"),
                            int(result.get("keyword_hit_count") or 0),
                            row["id"],
                        ),
                    )
                    conn.commit()
                state["analyzed"][item_id] = {
                    "is_recommended": bool(result.get("is_recommended")),
                    "at": result["backfilled_at"],
                }
                if item_id in state.get("failed_analyze", []):
                    state["failed_analyze"].remove(item_id)
                _status["ok"] += 1
            else:
                _status["failed"] += 1
                failed_list = state.setdefault("failed_analyze", [])
                if item_id not in failed_list:
                    failed_list.append(item_id)

            _status["done"] += 1
            flag = (
                "推荐" if result and result.get("is_recommended")
                else "不推荐" if result else "失败"
            )
            _push_recent(
                f"[{_status['done']}/{total}] {item_id} {flag}"
                + (f" · {result.get('value_score')}分" if result and result.get("value_score") is not None else "")
            )
            save_state(state)

    try:
        pending = [asyncio.create_task(analyze_one(row)) for row in targets]
        while pending:
            done, pending = await asyncio.wait(
                pending, timeout=0.5, return_when=asyncio.FIRST_COMPLETED
            )
            if _cancel_event is not None and _cancel_event.is_set():
                for task in pending:
                    task.cancel()
                _push_recent("已取消")
                break
    finally:
        cleanup_task_images("backfill")
        _status.update({
            "running": False,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "message": (
                f"完成：成功 {_status['ok']}，失败 {_status['failed']}"
                if _cancel_event is None or not _cancel_event.is_set()
                else f"已取消：成功 {_status['ok']}，失败 {_status['failed']}"
            ),
        })
        _cancel_event = None

    return get_status()


def cancel_analyze() -> bool:
    """请求取消当前分析任务。"""
    if _cancel_event is not None and _status.get("running"):
        _cancel_event.set()
        return True
    return False