import sqlite3
from datetime import datetime
from pathlib import Path

from src.services.sqlite_backup_service import run_sqlite_backup


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('hello')")
    conn.commit()
    conn.close()


def test_backup_creates_consistent_copy(tmp_path):
    db = tmp_path / "app.sqlite3"
    _make_db(db)

    target = run_sqlite_backup(
        str(db),
        backup_dir=tmp_path / "backups",
        now=datetime(2026, 1, 2, 3, 4, 5),
    )

    assert target == tmp_path / "backups" / "app-20260102-030405.sqlite3"
    conn = sqlite3.connect(target)
    try:
        assert conn.execute("SELECT v FROM t").fetchone()[0] == "hello"
    finally:
        conn.close()


def test_backup_prunes_oldest_beyond_keep(tmp_path):
    db = tmp_path / "app.sqlite3"
    _make_db(db)
    backup_dir = tmp_path / "backups"

    for day in range(1, 5):
        run_sqlite_backup(
            str(db),
            backup_dir=backup_dir,
            keep=2,
            now=datetime(2026, 1, day),
        )

    names = sorted(p.name for p in backup_dir.glob("app-*.sqlite3"))
    assert names == ["app-20260103-000000.sqlite3", "app-20260104-000000.sqlite3"]


def test_backup_missing_db_returns_none(tmp_path):
    assert run_sqlite_backup(
        str(tmp_path / "missing.sqlite3"),
        backup_dir=tmp_path / "backups",
    ) is None
