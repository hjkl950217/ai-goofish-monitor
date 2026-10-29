import sqlite3

from src.infrastructure.persistence.sqlite_connection import (
    SCHEMA_VERSION,
    init_schema,
)


def _open(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_fresh_db_writes_schema_version(tmp_path):
    conn = _open(str(tmp_path / "fresh.db"))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    cols = [r[1] for r in conn.execute("PRAGMA table_info(result_items)")]
    assert "initial_price" in cols
    assert "status" in cols
    conn.close()


def test_init_schema_reentrant_with_data(tmp_path):
    path = str(tmp_path / "again.db")
    conn = _open(path)
    conn.execute(
        "INSERT INTO favorite_items(item_id, link, created_at) VALUES ('1','https://x','t')"
    )
    conn.commit()
    conn.close()

    conn = _open(path)  # 重复执行不报错
    assert conn.execute("SELECT COUNT(1) FROM favorite_items").fetchone()[0] == 1
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


def test_legacy_v0_db_upgrades_without_duplicate_column(tmp_path):
    """模拟 NAS 老库：列已补齐、数据已有，但 user_version 还是 0。"""
    path = str(tmp_path / "legacy.db")
    conn = _open(path)
    conn.execute(
        "INSERT INTO favorite_items(item_id, link, created_at) VALUES ('9','https://y','t')"
    )
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    conn = _open(path)  # 升级不能重复加列报错、不能丢数据
    cols = [r[1] for r in conn.execute("PRAGMA table_info(result_items)")]
    assert {"initial_price", "last_checked_at", "content_hash", "status"} <= set(cols)
    assert conn.execute("SELECT COUNT(1) FROM favorite_items").fetchone()[0] == 1
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


def test_latest_db_skips_migration_probing(tmp_path, monkeypatch):
    path = str(tmp_path / "latest.db")
    conn = _open(path)
    conn.close()

    def _boom(_conn):
        raise AssertionError("已是最新版本，不应再逐列探测")

    monkeypatch.setattr(
        "src.infrastructure.persistence.sqlite_connection._migrate_result_items_status",
        _boom,
    )
    monkeypatch.setattr(
        "src.infrastructure.persistence.sqlite_connection._migrate_result_items_refresh",
        _boom,
    )
    conn = _open(path)
    conn.close()
