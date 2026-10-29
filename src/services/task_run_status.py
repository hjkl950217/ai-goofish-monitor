"""任务最近一次运行的结论。

子进程（spider_v2.py）结束时把它写进 `logs/.run_status_<task_id>.json`，
父进程退出时不需要解析日志就能知道这次是成功、空跑还是失败。
"""
import glob
import json
import os
from datetime import datetime
from typing import Optional

STATUS_PATTERN = ".run_status_*.json"


def status_path(task_id: int) -> str:
    return os.path.join("logs", f".run_status_{task_id}.json")


def write_run_status(
    path: str,
    *,
    task_name: str,
    status: str,
    item_count: int = 0,
    error: Optional[str] = None,
    reason: Optional[str] = None,
    items_seen: int = 0,
) -> None:
    payload = {
        "task_name": task_name,
        "status": status,
        "item_count": item_count,
        "error": error,
        "reason": reason,
        "items_seen": items_seen,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except OSError as exc:
        print(f"写入运行状态失败: {exc}")


def read_last_runs() -> dict:
    runs: dict = {}
    for path in glob.glob(os.path.join("logs", STATUS_PATTERN)):
        name = os.path.basename(path)
        try:
            task_id = int(name[len(".run_status_"):-len(".json")])
        except ValueError:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        data["task_id"] = task_id
        runs[str(task_id)] = data
    return runs
