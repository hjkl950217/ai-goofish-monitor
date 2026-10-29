"""
SQLite 定时备份服务：启动时备份一次，之后每 24 小时一次。
备份失败只打日志，不影响主流程。
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.persistence.sqlite_connection import get_database_path


BACKUP_DIR = "data/backups"
BACKUP_INTERVAL_SECONDS = 24 * 3600
DEFAULT_KEEP = 7


def run_sqlite_backup(
    db_path: str | None = None,
    *,
    backup_dir: str | Path = BACKUP_DIR,
    keep: int | None = None,
    now: datetime | None = None,
) -> Path | None:
    """用 VACUUM INTO 做一致性备份，返回备份文件路径；失败只打日志并返回 None。"""
    try:
        source = db_path or get_database_path()
        if not os.path.exists(source):
            print(f"SQLite 备份跳过：数据库文件不存在 ({source})")
            return None
        if keep is None:
            keep = _read_keep_count()
        target_dir = Path(backup_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        target = target_dir / f"app-{stamp}.sqlite3"
        conn = sqlite3.connect(source)
        try:
            conn.execute("VACUUM INTO ?", (str(target),))
        finally:
            conn.close()
        _prune_old_backups(target_dir, keep)
        print(f"SQLite 备份完成: {target}")
        return target
    except Exception as exc:
        print(f"SQLite 备份失败: {exc}")
        return None


def _read_keep_count() -> int:
    raw = env_manager.get_value("SQLITE_BACKUP_KEEP", str(DEFAULT_KEEP))
    try:
        keep = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_KEEP
    return keep if keep >= 1 else DEFAULT_KEEP


def _prune_old_backups(target_dir: Path, keep: int) -> None:
    backups = sorted(target_dir.glob("app-*.sqlite3"))
    for stale in backups[:-keep] if keep >= 1 else backups:
        try:
            stale.unlink()
        except OSError as exc:
            print(f"删除过期 SQLite 备份失败，已跳过: {stale} ({exc})")


async def sqlite_backup_loop(interval_seconds: int = BACKUP_INTERVAL_SECONDS) -> None:
    while True:
        run_sqlite_backup()
        await asyncio.sleep(interval_seconds)
