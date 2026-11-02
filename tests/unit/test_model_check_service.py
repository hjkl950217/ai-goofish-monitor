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
                "crawl_time": "2026-10-01T00:00:00",
                "keyword": TARGET,
                "task_name": TASK_NAME,
                "item_info": {
                    "item_id": item_id,
                    "title": title,
                    "price": "¥5000",
                    "description": "",
                    "link": f"https://www.goofish.com/item?id={item_id}",
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


def _fingerprint_for(*, title: str, description: str = "", target: str = TARGET,
                     task_name: str = TASK_NAME) -> str:
    """按服务同一算法算指纹，供测试直接造缓存记录。"""
    prompt = svc.load_prompt().replace("{{TARGET}}", target)
    return svc.compute_fingerprint(
        task_name=task_name,
        target=target,
        title=title,
        description=description,
        prompt=prompt,
    )


def test_global_regex_does_not_autopass_other_model_or_accessory(seeded_db, monkeypatch):
    """全局 regex 命中不再直接判匹配：别的型号、卖配件的都必须过 AI。"""
    monkeypatch.setenv("MODEL_CHECK_PREFILTER_REGEX", r"M1")

    fake = FakeClient(text='{"matched": false, "reason": "实际是 M1 85"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)
    outcome = _check(item_id="1", title="九号M1 85 准新车")
    assert outcome["matched"] is False
    assert outcome["source"] == "ai"
    assert fake.calls == 1

    fake.text = '{"matched": false, "reason": "出售的是电池配件"}'
    outcome = _check(item_id="1", title="适配九号M1 100 电池", description="可用，九号M1 100")
    assert outcome["matched"] is False
    assert outcome["source"] == "ai"
    assert fake.calls == 2


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


def test_ai_failure_returns_unknown_and_does_not_cache(seeded_db, monkeypatch):
    fake = FakeClient(error=RuntimeError("timeout"))
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    outcome = _check()
    assert outcome["matched"] is None
    assert "失败" in outcome["reason"]
    # 调用失败不写缓存，否则这条商品再也不会被重判
    assert svc.load_check("1", 0) is None


def test_unknown_verdict_is_not_cached(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": null, "reason": "标题未写型号"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    outcome = _check()
    assert outcome["matched"] is None
    assert svc.is_accepted(outcome) is False
    # null 不能长期缓存，否则这条商品再也不会被重判
    assert svc.load_check("1", 0) is None


def test_accepted_rules():
    assert svc.is_accepted({"matched": True, "source": "ai"}) is True
    assert svc.is_accepted({"matched": False, "source": "ai"}) is False
    # 只有明确匹配才放行；跳过校验、调用失败都拦掉，避免静默入库
    assert svc.is_accepted({"matched": None, "source": "skipped"}) is False
    assert svc.is_accepted({"matched": None, "source": "error"}) is False
    assert svc.is_accepted(None) is False


def test_cached_verdict_skips_second_call(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": true, "reason": "标题写明 M1 100"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    first = _check(item_id="2", title="九号M1 100 准新车")
    second = _check(item_id="2", title="九号M1 100 准新车")

    assert first["matched"] is True
    assert second["source"] == "cache"
    assert fake.calls == 1


def test_null_verdict_rejudged_after_text_added(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": null, "reason": "描述里没有型号"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    first = _check(item_id="1", title="九号M1 85 准新车", description="")
    assert first["matched"] is None

    fake.text = '{"matched": false, "reason": "实际是 M1 85"}'
    second = _check(item_id="1", title="九号M1 85 准新车", description="九号M1 85，带原装电池")
    assert second["matched"] is False
    assert fake.calls == 2


def test_target_change_invalidates_cache(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": true, "reason": "标题写明目标型号"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    first = _check(item_id="2", title="九号M1 100 准新车")
    assert first["matched"] is True

    second = asyncio.run(svc.check_item(
        item_id="2",
        task_name=TASK_NAME,
        target="九号N1 90",
        title="九号M1 100 准新车",
        description="",
    ))
    assert second["source"] == "ai"
    assert fake.calls == 2


def test_prompt_change_invalidates_cache(seeded_db, monkeypatch):
    fake = FakeClient(text='{"matched": true, "reason": "标题写明 M1 100"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)

    first = _check(item_id="2", title="九号M1 100 准新车")
    assert first["matched"] is True

    monkeypatch.setattr(svc, "load_prompt", lambda: "提示词改过了 {{TARGET}}")
    second = _check(item_id="2", title="九号M1 100 准新车")
    assert second["source"] == "ai"
    assert fake.calls == 2


def test_legacy_cache_without_fingerprint_is_rejudged(seeded_db, monkeypatch):
    """升级前的老记录没有指纹，不能当成有效缓存。"""
    with sqlite_connection() as conn:
        conn.execute(
            "INSERT INTO item_model_checks (item_id, task_id, matched, reason, checked_at)"
            " VALUES ('2', 0, 1, '旧记录无指纹', '2026-10-01T00:00:00')"
        )
        conn.commit()

    fake = FakeClient(text='{"matched": true, "reason": "标题写明 M1 100"}')
    monkeypatch.setattr(svc, "_get_client", lambda: fake)
    outcome = _check(item_id="2", title="九号M1 100 准新车")
    assert outcome["source"] == "ai"
    assert fake.calls == 1


def test_legacy_null_cache_is_ignored_on_read(seeded_db):
    """旧 null 缓存读取时失效。"""
    with sqlite_connection() as conn:
        conn.execute(
            "INSERT INTO item_model_checks (item_id, task_id, matched, reason, checked_at)"
            " VALUES ('2', 0, NULL, '判不出', '2026-10-01T00:00:00')"
        )
        conn.commit()
    assert svc.load_check("2", 0) is None


def test_backfill_skips_already_checked(seeded_db):
    fingerprint = _fingerprint_for(title="九号M1 85 准新车")
    svc.save_check("1", 0, False, "是 M1 85", "2026-10-01T00:00:00", fingerprint)
    pending = backfill.fetch_candidates()
    assert [row["item_id"] for row in pending] == ["2"]


def test_backfill_rechecks_stale_cache(seeded_db):
    """指纹对不上或结论是 null 的旧缓存，复查都要重判。"""
    with sqlite_connection() as conn:
        conn.execute(
            "INSERT INTO item_model_checks (item_id, task_id, matched, reason, checked_at,"
            " input_fingerprint) VALUES ('1', 0, NULL, '判不出', '2026-10-01T00:00:00', ?)",
            (_fingerprint_for(title="九号M1 85 准新车"),),
        )
        conn.execute(
            "INSERT INTO item_model_checks (item_id, task_id, matched, reason, checked_at,"
            " input_fingerprint) VALUES ('2', 0, 1, '旧输入', '2026-10-01T00:00:00', 'deadbeef')"
        )
        conn.commit()
    pending = backfill.fetch_candidates()
    assert sorted(row["item_id"] for row in pending) == ["1", "2"]


def test_backfill_removes_unknown_verdict(seeded_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def fake_check(**kwargs):
        return {"matched": None, "reason": "标题未写型号", "source": "ai"}

    monkeypatch.setattr(backfill.model_check_service, "check_item", fake_check)
    status = asyncio.run(backfill.run_check(workers=1))

    assert status["removed"] == 2
    with sqlite_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM result_items").fetchone()[0] == 0


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


def test_remove_result_cleans_images_from_other_task_dirs(seeded_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    other_task_dir = tmp_path / "images" / "task_images_另一个任务"
    other_task_dir.mkdir(parents=True)
    target = other_task_dir / "product_1_1_b.jpg"
    bystander = other_task_dir / "product_2_1_b.jpg"
    target.write_bytes(b"x")
    bystander.write_bytes(b"x")

    backfill.remove_result(FILENAME, "1", TASK_NAME)

    assert target.exists() is False
    assert bystander.exists() is True
