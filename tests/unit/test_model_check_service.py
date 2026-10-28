import asyncio
import json

import pytest

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services import model_check_backfill_service as backfill
from src.services import model_check_service as svc

FILENAME = "九号M1_100_full_data.jsonl"
TASK_NAME = "九号捡漏-M1100"
TARGET = "九号M1 100"


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "t.sqlite3"))
    monkeypatch.setenv("MODEL_CHECK_PREFILTER_REGEX", "")
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                id, task_name, enabled, keyword, description, analyze_images, max_pages,
                personal_only, min_price, max_price, cron, ai_prompt_base_file,
                ai_prompt_criteria_file, account_state_file, account_strategy,
                free_shipping, new_publish_option, region, decision_mode,
                keyword_rules_json, is_running
            ) VALUES (0, ?, 1, ?, '', 0, 3, 1, NULL, NULL, '', 'prompts/base_prompt.txt',
                      '', NULL, 'auto', 0, NULL, NULL, 'ai', '[]', 0)
            """,
            (TASK_NAME, TARGET),
        )
        for item_id, title in (("1", "九号M1 85 准新车"), ("2", "九号M1 100 准新车")):
            record = {
                "爬取时间": "2026-10-01T00:00:00",
                "搜索关键字": TARGET,
                "任务名称": TASK_NAME,
                "商品信息": {
                    "商品ID": item_id,
                    "商品标题": title,
                    "当前售价": "¥5000",
                    "商品描述": "",
                    "商品链接": f"https://www.goofish.com/item?id={item_id}",
                },
            }
            conn.execute(
                """
                INSERT INTO result_items (
                    result_filename, keyword, task_name, crawl_time, price, initial_price,
                    price_display, item_id, title, link, link_unique_key, is_recommended,
                    analysis_source, keyword_hit_count, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    FILENAME, TARGET, TASK_NAME, "2026-10-01T00:00:00", 5000.0, 5000.0,
                    "¥5000", item_id, title, f"https://www.goofish.com/item?id={item_id}",
                    f"item:{item_id}", 0, "ai", 0, json.dumps(record, ensure_ascii=False),
                ),
            )
        conn.commit()


class FakeClient:
    def __init__(self, text: str = "", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.text


def _check(item_id="1", title="九号M1 85 准新车", description=""):
    return asyncio.run(
        svc.check_item(
            item_id=item_id,
            task_name=TASK_NAME,
            target=TARGET,
            title=title,
            description=description,
        )
    )


def test_prefilter_skipped_when_regex_is_blank(monkeypatch):
    monkeypatch.setenv("MODEL_CHECK_PREFILTER_REGEX", "")
    assert svc.prefilter_passes("九号M1 100") is False


def test_prefilter_only_lets_through(monkeypatch):
    monkeypatch.setenv("MODEL_CHECK_PREFILTER_REGEX", r"M1\s*[-‑_]?\s*100")
    assert svc.prefilter_passes("九号M1100 准新车") is True
    assert svc.prefilter_passes("九号M1 85") is False


def test_disabled_switch_skips(seeded_db, monkeypatch):
    monkeypatch.setenv("MODEL_CHECK_ENABLED", "false")
    assert svc.is_usable() is False
    outcome = _check()
    assert outcome["matched"] is None
    assert outcome["source"] == "skipped"


def test_mismatch_is_stored(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": false, "reason": "实际是 M1 85"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    outcome = _check()
    assert outcome["matched"] is False
    assert outcome["source"] == "ai"

    cached = svc.load_check("1", 0)
    assert cached["matched"] is False
    assert "M1 85" in cached["reason"]


def test_ai_failure_falls_open(seeded_db, monkeypatch):
    fake = FakeClient(error=RuntimeError("timeout"))
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    outcome = _check()
    assert outcome["matched"] is None
    assert "失败" in outcome["reason"]


def test_cached_verdict_skips_second_call(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": true, "reason": "标题写明 M1 100"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    first = _check(item_id="2", title="九号M1 100 准新车")
    second = _check(item_id="2", title="九号M1 100 准新车")

    assert first["matched"] is True
    assert second["source"] == "cache"
    assert fake.calls == 1


def test_backfill_skips_already_checked(seeded_db):
    svc.save_check("1", 0, False, "是 M1 85", "2026-10-01T00:00:00")
    pending = backfill.fetch_candidates()
    assert [row["item_id"] for row in pending] == ["2"]


def test_remove_result_deletes_row_and_images(seeded_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    image_dir = tmp_path / "images" / f"task_images_{TASK_NAME}"
    image_dir.mkdir(parents=True)
    keep = image_dir / "product_2_1_a.jpg"
    drop = image_dir / "product_1_1_a.jpg"
    keep.write_bytes(b"x")
    drop.write_bytes(b"x")

    backfill.remove_result(FILENAME, "1", TASK_NAME)

    assert drop.exists() is False
    assert keep.exists() is True
    with sqlite_connection() as conn:
        remaining = [r["item_id"] for r in conn.execute("SELECT item_id FROM result_items")]
    assert remaining == ["2"]
