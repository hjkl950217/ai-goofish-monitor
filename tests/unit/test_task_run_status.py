from src.services import task_run_status as trs


def test_write_then_read_run_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()

    trs.write_run_status(
        trs.status_path(7),
        task_name="九号捡漏-N190",
        status="empty",
        reason="search_empty",
        items_seen=0,
    )

    runs = trs.read_last_runs()
    assert runs["7"]["status"] == "empty"
    assert runs["7"]["reason"] == "search_empty"
    assert runs["7"]["task_name"] == "九号捡漏-N190"


def test_read_skips_unparsable_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / ".run_status_x.json").write_text("{}", encoding="utf-8")
    (tmp_path / "logs" / ".run_status_3.json").write_text("not json", encoding="utf-8")

    assert trs.read_last_runs() == {}
