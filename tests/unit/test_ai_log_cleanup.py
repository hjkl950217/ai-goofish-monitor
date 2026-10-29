from datetime import datetime, timedelta
from pathlib import Path

from src.ai_handler import cleanup_ai_logs


def _write_log(directory: Path, days_ago: int) -> Path:
    stamp = datetime.now() - timedelta(days=days_ago)
    path = directory / f"{stamp.strftime('%Y%m%d_%H%M%S')}.log"
    path.write_text("{}", encoding="utf-8")
    return path


def test_retention_days_read_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LOG_RETENTION_DAYS", "3")
    old = _write_log(tmp_path, 5)
    fresh = _write_log(tmp_path, 1)

    cleanup_ai_logs(str(tmp_path))

    assert not old.exists()
    assert fresh.exists()


def test_default_retention_is_one_day(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_LOG_RETENTION_DAYS", raising=False)
    old = _write_log(tmp_path, 2)
    fresh = _write_log(tmp_path, 0)

    cleanup_ai_logs(str(tmp_path))

    assert not old.exists()
    assert fresh.exists()


def test_invalid_env_falls_back_to_one_day(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LOG_RETENTION_DAYS", "abc")
    old = _write_log(tmp_path, 2)

    cleanup_ai_logs(str(tmp_path))

    assert not old.exists()
