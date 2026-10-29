"""通知发送记录。

每条一条 JSONL 追加到 logs/notifications.jsonl，超过上限时只保留最近的部分。
"""
import json
import os
from datetime import datetime
from typing import List

HISTORY_PATH = os.path.join("logs", "notifications.jsonl")
MAX_LINES = 500


def record(
    *,
    channel: str,
    label: str,
    success: bool,
    message: str,
    title: str,
    is_test: bool = False,
) -> None:
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "channel": channel,
        "label": label,
        "success": bool(success),
        "message": message,
        "title": title,
        "is_test": is_test,
    }
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH) or ".", exist_ok=True)
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _trim()
    except OSError as exc:
        print(f"写入通知记录失败: {exc}")


def _trim() -> None:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    if len(lines) <= MAX_LINES:
        return
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines[-MAX_LINES:])
    except OSError as exc:
        print(f"裁剪通知记录失败: {exc}")


def read_recent(limit: int = 50) -> List[dict]:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    records = []
    for line in lines[-max(1, limit):]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))
