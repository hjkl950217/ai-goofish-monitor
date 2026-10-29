from src.services import notification_history as nh


def test_record_and_read_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(nh, "HISTORY_PATH", str(tmp_path / "notifications.jsonl"))

    nh.record(channel="bark", label="Bark", success=True, message="ok", title="商品A")
    nh.record(channel="telegram", label="Telegram", success=False, message="boom", title="商品B", is_test=True)

    records = nh.read_recent(10)
    assert [item["channel"] for item in records] == ["telegram", "bark"]
    assert records[0]["is_test"] is True
    assert records[1]["success"] is True


def test_read_recent_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(nh, "HISTORY_PATH", str(tmp_path / "nope.jsonl"))
    assert nh.read_recent(5) == []
