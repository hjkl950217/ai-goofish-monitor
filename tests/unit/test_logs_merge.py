import asyncio

from src.api.routes.logs import _read_merged_lines


def test_merged_lines_sorted_by_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "a_1.log").write_text(
        "[ 2026-10-29 10:00:01] A1\n[ 2026-10-29 10:00:05] A2\n", encoding="utf-8"
    )
    (tmp_path / "logs" / "b_2.log").write_text(
        "[ 2026-10-29 10:00:03] B1\n", encoding="utf-8"
    )

    lines = asyncio.run(_read_merged_lines(10))

    assert lines == [
        "[a_1] [ 2026-10-29 10:00:01] A1",
        "[b_2] [ 2026-10-29 10:00:03] B1",
        "[a_1] [ 2026-10-29 10:00:05] A2",
    ]


def test_merged_lines_keeps_continuation_lines_with_previous_timestamp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "a_1.log").write_text(
        "[ 2026-10-29 10:00:01] A1\nTraceback line\n", encoding="utf-8"
    )
    (tmp_path / "logs" / "b_2.log").write_text(
        "[ 2026-10-29 10:00:00] B1\n", encoding="utf-8"
    )

    lines = asyncio.run(_read_merged_lines(10))

    assert lines == ["[b_2] [ 2026-10-29 10:00:00] B1", "[a_1] [ 2026-10-29 10:00:01] A1", "[a_1] Traceback line"]
