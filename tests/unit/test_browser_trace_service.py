import asyncio
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from src.services import browser_trace_service as trace


def test_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_BROWSER_TRACE", "")
    monkeypatch.setenv("AGM_TRACE_DIR", str(tmp_path))

    assert trace.is_enabled() is False
    assert trace.start("任务") is None


def test_start_creates_session_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_BROWSER_TRACE", "true")
    monkeypatch.setenv("AGM_TRACE_DIR", str(tmp_path))

    session = trace.start("九号捡漏-M1100", "state/a.json")
    assert session is not None
    try:
        session.close()
    finally:
        pass

    path = Path(session.path)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    assert meta["task_name"] == "九号捡漏-M1100"
    assert meta["state_file"] == "state/a.json"
    assert (path / "network.jsonl").exists()


def test_start_never_collides(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_BROWSER_TRACE", "true")
    monkeypatch.setenv("AGM_TRACE_DIR", str(tmp_path))

    first = trace.start("任务")
    second = trace.start("任务")
    first.close()
    second.close()

    assert first.path != second.path


def test_start_sanitizes_task_name(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_BROWSER_TRACE", "true")
    monkeypatch.setenv("AGM_TRACE_DIR", str(tmp_path))

    session = trace.start("a/b c")
    session.close()

    assert "/" not in Path(session.path).name
    assert " " not in Path(session.path).name


def _response(url, resource_type="xhr", headers=None):
    return SimpleNamespace(
        url=url,
        request=SimpleNamespace(resource_type=resource_type),
        headers=headers or {},
    )


def test_wanted_keeps_target_hosts_and_api_types():
    assert trace.TraceSession._wanted(_response("https://www.goofish.com/x")) is True
    assert trace.TraceSession._wanted(_response("https://h5api.m.taobao.com/x")) is True
    assert trace.TraceSession._wanted(_response("https://example.com/x")) is False


def test_wanted_keeps_static_response_with_set_cookie():
    response = _response(
        "https://www.goofish.com/img.png",
        resource_type="image",
        headers={"Set-Cookie": "cookie2=abc"},
    )
    assert trace.TraceSession._wanted(response) is True


def test_set_cookie_header_is_case_insensitive():
    response = _response(
        "https://www.goofish.com/img.png",
        resource_type="image",
        headers={"set-cookie": "cookie2=abc"},
    )
    assert trace.TraceSession._wanted(response) is True


def test_list_traces_reports_files_and_size(tmp_path):
    first = tmp_path / "b_task_20260101_000000"
    second = tmp_path / "a_task_20260101_000000"
    for folder in (first, second):
        folder.mkdir()
        (folder / "network.jsonl").write_text("{}\n", encoding="utf-8")

    items = trace.list_traces(str(tmp_path))

    assert [item["name"] for item in items] == [
        "b_task_20260101_000000",
        "a_task_20260101_000000",
    ]
    assert items[0]["files"][0]["name"] == "network.jsonl"
    assert items[0]["size"] == (first / "network.jsonl").stat().st_size
    assert "mtime" in items[0]


def test_list_traces_missing_dir(tmp_path):
    assert trace.list_traces(str(tmp_path / "nope")) == []


class _FakeRequest:
    def __init__(self, method="GET", resource_type="xhr", headers=None, post_data=None):
        self.method = method
        self.resource_type = resource_type
        self.headers = headers or {}
        self.post_data = post_data


class _FakeBodyResponse:
    def __init__(self, url, headers, body=b"{}", request=None, status=200):
        self.url = url
        self.headers = headers
        self._body = body
        self.request = request or _FakeRequest()
        self.status = status

    async def body(self):
        return self._body


def test_dump_writes_one_line(tmp_path):
    session = trace.TraceSession(str(tmp_path))
    response = _FakeBodyResponse(
        "https://www.goofish.com/api",
        {"content-type": "application/json", "set-cookie": "cookie2=abc"},
        body=b'{"ok":true}',
        request=_FakeRequest(method="POST", post_data='{"q":"M1 100"}'),
    )

    asyncio.run(session._dump(response))
    session.close()

    lines = (tmp_path / "network.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["set_cookie"] == "cookie2=abc"
    assert record["request_body"] == '{"q":"M1 100"}'
    assert record["body"] == '{"ok":true}'
    assert record["resource_type"] == "xhr"


def test_snapshot_writes_cookies_and_storage(tmp_path):
    class FakeContext:
        async def cookies(self):
            return [{"name": "unb", "value": "1"}]

    class FakePage:
        async def evaluate(self, script):
            return {
                "localStorage": {"k": "v"},
                "sessionStorage": {},
                "caches": [],
                "indexedDB": [],
            }

    session = trace.TraceSession(str(tmp_path))
    asyncio.run(session.snapshot(FakeContext(), FakePage()))
    session.close()

    assert json.loads((tmp_path / "cookies.json").read_text(encoding="utf-8")) == [
        {"name": "unb", "value": "1"}
    ]
    storage = json.loads((tmp_path / "storage.json").read_text(encoding="utf-8"))
    assert storage["localStorage"] == {"k": "v"}


def _fill_session(path: Path, size: int) -> None:
    path.mkdir()
    (path / "network.jsonl").write_bytes(b"x" * size)


def test_enforce_size_limit_deletes_oldest(tmp_path, monkeypatch):
    monkeypatch.setenv(trace.MAX_MB_ENV, "1")
    old = tmp_path / "task_20260101_000000"
    new = tmp_path / "task_20260102_000000"
    _fill_session(old, 800 * 1024)
    _fill_session(new, 800 * 1024)
    past = time.time() - 1000
    os.utime(old, (past, past))

    trace._enforce_size_limit(str(tmp_path))

    assert not old.exists()
    assert new.exists()


def test_enforce_size_limit_under_limit_keeps_all(tmp_path, monkeypatch):
    monkeypatch.setenv(trace.MAX_MB_ENV, "200")
    session = tmp_path / "task_20260101_000000"
    _fill_session(session, 1024)

    trace._enforce_size_limit(str(tmp_path))

    assert session.exists()


def test_enforce_size_limit_invalid_env_keeps_all(tmp_path, monkeypatch):
    monkeypatch.setenv(trace.MAX_MB_ENV, "abc")
    session = tmp_path / "task_20260101_000000"
    _fill_session(session, 1024)

    trace._enforce_size_limit(str(tmp_path))

    assert session.exists()


def test_start_enforces_size_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("AGM_BROWSER_TRACE", "true")
    monkeypatch.setenv("AGM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv(trace.MAX_MB_ENV, "1")
    old = tmp_path / "old_task_20260101_000000"
    _fill_session(old, 1200 * 1024)

    session = trace.start("new task")
    try:
        assert session is not None
        assert not old.exists()
        assert Path(session.path).exists()
    finally:
        session.close()
