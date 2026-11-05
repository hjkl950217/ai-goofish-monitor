import asyncio
import json
from pathlib import Path

import pytest

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services import reanalyze_service as svc


@pytest.fixture()
def analysis_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "analysis.sqlite3"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(svc, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(svc, "_lock", asyncio.Lock())
    monkeypatch.setattr(svc, "_status", {"running": False, "recent": []})
    bootstrap_sqlite_storage()
    base = tmp_path / "base.txt"
    base.write_text("分析标准：\n{{CRITERIA_SECTION}}", encoding="utf-8")
    with sqlite_connection() as conn:
        for task_id, name, keyword in ((1, "任务M1100", "九号M1 100"), (2, "任务N190", "九号N1 90")):
            conn.execute(
                """INSERT INTO tasks (
                    id, task_name, enabled, keyword, description, analyze_images, max_pages,
                    personal_only, cron, ai_prompt_base_file, ai_prompt_criteria_file,
                    account_strategy, free_shipping, decision_mode, keyword_rules_json,
                    is_running, criteria_text
                ) VALUES (?, ?, 1, ?, '', 0, 1, 0, '', ?, '', 'auto', 0, 'ai', '[]', 0, ?)""",
                (task_id, name, keyword, str(base), "目标=" + keyword + "；必须核对商品型号。" * 30),
            )
        conn.commit()

    def add_item(item_id, task_name, keyword):
        record = {
            "task_name": task_name, "keyword": keyword,
            "item_info": {"item_id": item_id, "title": keyword, "price": "¥5000"},
            "ai_analysis": {"is_recommended": False, "reason": "旧结论"},
        }
        with sqlite_connection() as conn:
            conn.execute(
                """INSERT INTO result_items (
                    result_filename, keyword, task_name, crawl_time, price, price_display,
                    item_id, title, link, link_unique_key, is_recommended,
                    analysis_source, keyword_hit_count, raw_json
                ) VALUES (?, ?, ?, '2026-11-01T10:00:00', 5000, '¥5000', ?, ?, ?, ?, 0, 'ai', 0, ?)""",
                (keyword + "_full_data.jsonl", keyword, task_name, item_id, keyword,
                 "https://www.goofish.com/item?id=" + item_id, "item:" + item_id,
                 json.dumps(record, ensure_ascii=False)),
            )
            conn.commit()
    return add_item


def test_reanalysis_uses_each_items_own_task_criteria(analysis_db, monkeypatch):
    import src.ai_handler as handler

    analysis_db("m1", "任务M1100", "九号M1 100")
    analysis_db("n1", "任务N190", "九号N1 90")

    async def analyze(record, images, prompt):
        keyword = record["keyword"]
        return {"is_recommended": "目标=" + keyword in prompt, "reason": "本任务标准"}

    monkeypatch.setattr(handler, "get_ai_analysis", analyze)
    result = asyncio.run(svc.run_analyze(scope="all", workers=1))

    with sqlite_connection() as conn:
        rows = conn.execute("SELECT item_id, is_recommended FROM result_items ORDER BY item_id").fetchall()
    assert [(row["item_id"], row["is_recommended"]) for row in rows] == [("m1", 1), ("n1", 1)]
    assert result["ok"] == 2
    assert result["failed"] == 0


def test_reanalysis_missing_task_does_not_borrow_another_tasks_criteria(analysis_db, monkeypatch):
    import src.ai_handler as handler

    analysis_db("orphan", "不存在的任务", "不存在的型号")

    async def analyze(record, images, prompt):
        return {"is_recommended": True, "reason": "不应该发起本次分析"}

    monkeypatch.setattr(handler, "get_ai_analysis", analyze)
    result = asyncio.run(svc.run_analyze(scope="all", workers=1))

    assert result["total"] == 0
    assert result["ok"] == 0
    assert result["failed"] == 0
    assert any("已跳过 1 条" in line for line in result["recent"])
    with sqlite_connection() as conn:
        row = conn.execute("SELECT raw_json, is_recommended FROM result_items WHERE item_id='orphan'").fetchone()
    assert row["is_recommended"] == 0
    assert json.loads(row["raw_json"])["ai_analysis"]["reason"] == "旧结论"


def test_failed_item_reports_reason_on_its_own_progress_line(analysis_db, monkeypatch):
    import src.ai_handler as handler

    analysis_db("m1", "任务M1100", "九号M1 100")

    async def analyze(record, images, prompt):
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "get_ai_analysis", analyze)
    result = asyncio.run(svc.run_analyze(scope="all", workers=1))

    assert any(line == "[1/1] m1 失败 · boom" for line in result["recent"])
    assert not any(line.startswith("[x]") for line in result["recent"])


def test_reanalysis_skips_orphan_and_analyzes_rest(analysis_db, monkeypatch):
    import src.ai_handler as handler

    analysis_db("m1", "任务M1100", "九号M1 100")
    analysis_db("orphan", "不存在的任务", "不存在的型号")
    analyzed = []

    async def analyze(record, images, prompt):
        analyzed.append(record["item_info"]["item_id"])
        return {"is_recommended": True, "reason": "本任务标准"}

    monkeypatch.setattr(handler, "get_ai_analysis", analyze)
    result = asyncio.run(svc.run_analyze(scope="all", workers=1))

    assert result["total"] == 1
    assert result["ok"] == 1
    assert result["failed"] == 0
    assert analyzed == ["m1"]
