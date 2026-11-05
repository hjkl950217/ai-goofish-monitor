import asyncio
import json

import pytest

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services import item_manual_refresh_service, result_storage_service

FILENAME = "测试车_full_data.jsonl"

# item_id, status 列, raw_json 里的 item_info.status, crawl_time
SEED_ROWS = [
    ("A", "active", "在线", "2026-10-04T00:00:00"),
    ("B", "active", "卖掉了", "2026-10-03T00:00:00"),
    ("C", "expired", "已下架", "2026-10-02T00:00:00"),
    ("D", "hidden", "在线", "2026-10-01T00:00:00"),
]


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "t.sqlite3"))
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        for item_id, status, status_text, crawl_time in SEED_ROWS:
            record = {
                "crawl_time": crawl_time,
                "keyword": "测试车",
                "task_name": "T",
                "item_info": {
                    "item_id": item_id,
                    "title": f"标题{item_id}",
                    "price": "¥5000",
                    "status": status_text,
                    "link": f"https://www.goofish.com/item?id={item_id}",
                },
            }
            conn.execute(
                """
                INSERT INTO result_items (
                    result_filename, keyword, task_name, crawl_time, publish_time, price,
                    initial_price, price_display, item_id, title, link, link_unique_key,
                    seller_nickname, is_recommended, analysis_source, keyword_hit_count,
                    status, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    FILENAME,
                    "测试车",
                    "T",
                    crawl_time,
                    None,
                    5000.0,
                    5000.0,
                    "¥5000",
                    item_id,
                    f"标题{item_id}",
                    f"https://www.goofish.com/item?id={item_id}",
                    f"item:{item_id}",
                    "卖家",
                    0,
                    None,
                    0,
                    status,
                    json.dumps(record, ensure_ascii=False),
                ),
            )
        conn.commit()


def _query_visible():
    return asyncio.run(
        result_storage_service.query_result_records(
            FILENAME,
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            page=1,
            limit=10,
            include_hidden=False,
        )
    )


def test_sold_item_visible_and_sorted_after_active(seeded_db):
    _, records = _query_visible()
    ids = [record["item_info"]["item_id"] for record in records]

    assert "D" not in ids
    assert set(ids) == {"A", "B", "C"}
    assert ids[0] == "A"
    assert set(ids[-2:]) == {"B", "C"}

    sold = next(record for record in records if record["item_info"]["item_id"] == "B")
    assert sold["_status"] == "expired"
    assert sold["_effective_hidden"] is False
    assert sold["_hidden_reason"] == "expired"


def test_visible_item_ids_exclude_sold(seeded_db):
    assert result_storage_service.load_visible_result_item_ids(FILENAME) == {"A"}


def _load_row(conn, item_id):
    return conn.execute(
        "SELECT id, price, raw_json FROM result_items WHERE item_id = ?", (item_id,)
    ).fetchone()


def _write_status(item_id, status_text):
    with sqlite_connection() as conn:
        row = _load_row(conn, item_id)
    item_manual_refresh_service._write_back(row, {"status": status_text})


def _read_status(item_id):
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT status FROM result_items WHERE item_id = ?", (item_id,)
        ).fetchone()
    return row["status"]


def test_write_back_marks_sold_as_expired(seeded_db):
    _write_status("A", "卖掉了")
    assert _read_status("A") == "expired"


def test_write_back_keeps_manual_hidden(seeded_db):
    _write_status("D", "在线")
    assert _read_status("D") == "hidden"
