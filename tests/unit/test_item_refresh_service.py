import json

import pytest

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services import item_refresh_service as svc

FILENAME = "测试车_full_data.jsonl"
ITEM_ID = "1"


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "t.sqlite3"))
    bootstrap_sqlite_storage()
    record = {
        "crawl_time": "2026-10-01T00:00:00",
        "keyword": "测试车",
        "task_name": "T",
        "item_info": {
            "item_id": ITEM_ID,
            "title": "标题",
            "price": "¥5000",
            "description": "旧描述",
            "link": f"https://www.goofish.com/item?id={ITEM_ID}",
        },
    }
    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT INTO result_items (
                result_filename, keyword, task_name, crawl_time, publish_time, price,
                initial_price, price_display, item_id, title, link, link_unique_key,
                seller_nickname, is_recommended, analysis_source, keyword_hit_count,
                raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                FILENAME,
                "测试车",
                "T",
                "2026-10-01T00:00:00",
                None,
                5000.0,
                5000.0,
                "¥5000",
                ITEM_ID,
                "标题",
                f"https://www.goofish.com/item?id={ITEM_ID}",
                f"item:{ITEM_ID}",
                "卖家",
                1,
                "ai",
                0,
                json.dumps(record, ensure_ascii=False),
            ),
        )
        conn.commit()


def test_fingerprint_reacts_to_price_and_description():
    base = svc.build_content_fingerprint("¥5000", "旧描述")
    assert base == svc.build_content_fingerprint("¥5000", "旧描述")
    assert base != svc.build_content_fingerprint("¥4500", "旧描述")
    assert base != svc.build_content_fingerprint("¥5000", "新描述")


def test_is_offline_status():
    assert svc.is_offline_status("在线") is False
    assert svc.is_offline_status("已下架") is True
    assert svc.is_offline_status("宝贝已售出") is True
    assert svc.is_offline_status("") is False


def test_price_change_updates_latest_but_keeps_initial(seeded_db):
    outcome = svc.record_refresh(
        result_filename=FILENAME,
        item_id=ITEM_ID,
        price=4500.0,
        description="旧描述",
    )
    assert outcome["changed"] is True

    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT price, initial_price, price_display, raw_json"
            " FROM result_items WHERE item_id = ?",
            (ITEM_ID,),
        ).fetchone()
    assert row["price"] == 4500.0
    assert row["initial_price"] == 5000.0
    assert row["price_display"] == "¥4500"
    assert json.loads(row["raw_json"])["item_info"]["price"] == "¥4500"


def test_unchanged_item_only_touches_last_checked(seeded_db):
    first = svc.record_refresh(
        result_filename=FILENAME, item_id=ITEM_ID, price=5000.0, description="旧描述"
    )
    assert first["changed"] is False

    second = svc.record_refresh(
        result_filename=FILENAME, item_id=ITEM_ID, price=5000.0, description="旧描述"
    )
    assert second["changed"] is False

    changed = svc.record_refresh(
        result_filename=FILENAME, item_id=ITEM_ID, price=5000.0, description="新描述"
    )
    assert changed["changed"] is True


def test_image_count_change_updates_list_without_reanalysis(seeded_db):
    outcome = svc.record_refresh(
        result_filename=FILENAME,
        item_id=ITEM_ID,
        price=5000.0,
        description="旧描述",
        image_urls=["http://img/1.jpg", "http://img/2.jpg"],
    )
    assert outcome["images_changed"] is True
    assert outcome["changed"] is False

    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT raw_json FROM result_items WHERE item_id = ?", (ITEM_ID,)
        ).fetchone()
    info = json.loads(row["raw_json"])["item_info"]
    assert info["images"] == ["http://img/1.jpg", "http://img/2.jpg"]
    assert info["main_image"] == "http://img/1.jpg"


def test_offline_item_is_marked_expired(seeded_db):
    outcome = svc.record_refresh(
        result_filename=FILENAME, item_id=ITEM_ID, offline=True
    )
    assert outcome["offline"] is True

    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT status FROM result_items WHERE item_id = ?", (ITEM_ID,)
        ).fetchone()
    assert row["status"] == "expired"

    targets = svc.pick_refresh_targets(FILENAME, per_run=10)
    assert targets == []
