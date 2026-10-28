import asyncio
import json

from src.services.account_state_store import merge_and_save, read_expiry

COOKIE2 = {"name": "cookie2", "value": "old", "domain": ".taobao.com", "path": "/"}
UNB = {"name": "unb", "value": "u1", "domain": ".taobao.com", "path": "/"}


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_merge_keeps_fingerprint_fields(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {
        "capturedAt": "2026-10-01T00:00:00Z",
        "env": {"navigator": {"userAgent": "UA-1"}},
        "headers": {"User-Agent": "UA-1"},
        "storage": {"local": {"k": "v"}},
        "cookies": [COOKIE2],
    })

    merge_and_save(str(path), {"cookies": [{**COOKIE2, "value": "new"}]})

    saved = _read(path)
    assert saved["capturedAt"] == "2026-10-01T00:00:00Z"
    assert saved["env"]["navigator"]["userAgent"] == "UA-1"
    assert saved["headers"]["User-Agent"] == "UA-1"
    assert saved["storage"]["local"] == {"k": "v"}
    assert saved["cookies"][0]["value"] == "new"


def test_merge_keeps_cookies_missing_from_new_state(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [COOKIE2, UNB]})
    new = {"name": "cookie2", "value": "new", "domain": ".taobao.com", "path": "/"}

    merge_and_save(str(path), {"cookies": [new]})

    values = {cookie["name"]: cookie["value"] for cookie in _read(path)["cookies"]}
    assert values == {"cookie2": "new", "unb": "u1"}


def test_same_name_different_domain_is_kept_separately(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [{**UNB, "domain": ".goofish.com"}]})
    new = {**UNB, "value": "u2", "domain": ".taobao.com"}

    merge_and_save(str(path), {"cookies": [new]})

    domains = {cookie["domain"]: cookie["value"] for cookie in _read(path)["cookies"]}
    assert domains == {".goofish.com": "u1", ".taobao.com": "u2"}


def test_origins_replaced_only_when_original_has_them(tmp_path):
    standard = tmp_path / "standard.json"
    _write(standard, {"cookies": [], "origins": [{"origin": "https://a", "localStorage": []}]})
    enhanced = tmp_path / "enhanced.json"
    _write(enhanced, {"env": {"navigator": {}}, "cookies": []})

    state = {"cookies": [COOKIE2], "origins": [{"origin": "https://b", "localStorage": []}]}
    merge_and_save(str(standard), state)
    merge_and_save(str(enhanced), state)

    assert _read(standard)["origins"][0]["origin"] == "https://b"
    assert "origins" not in _read(enhanced)


def test_empty_cookies_leave_file_untouched(tmp_path):
    path = tmp_path / "acc.json"
    original = json.dumps({"cookies": [COOKIE2]}, ensure_ascii=False)
    path.write_text(original, encoding="utf-8")

    assert merge_and_save(str(path), {"cookies": []}) is False
    assert path.read_text(encoding="utf-8") == original


def test_merge_uses_separate_lock_file(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [COOKIE2]})

    merge_and_save(str(path), {"cookies": [COOKIE2]})

    assert (tmp_path / "acc.json.lock").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_expiry_prefers_login_cookie(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [
        {"name": "_m_h5_tk", "expires": 1000},
        {**UNB, "expires": 3000},
        {**COOKIE2, "expires": 2000},
    ]})

    assert read_expiry(str(path)) == 2000


def test_read_expiry_skips_session_cookie(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [
        {**COOKIE2, "expires": -1},
        {**UNB, "expires": 3000},
    ]})

    assert read_expiry(str(path)) == 3000


def test_read_expiry_ignores_short_term_tokens(tmp_path):
    path = tmp_path / "acc.json"
    _write(path, {"cookies": [{"name": "_m_h5_tk", "expires": 1000}]})

    assert read_expiry(str(path)) is None


class _FakeContext:
    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error

    async def storage_state(self):
        if self.error:
            raise self.error
        return self.state


def test_scraper_collects_then_flushes_once(tmp_path, monkeypatch):
    from src.scraper import _collect_login_state, _flush_login_states

    path = tmp_path / "acc.json"
    _write(path, {"env": {"navigator": {"userAgent": "UA-1"}}, "cookies": [COOKIE2]})
    monkeypatch.chdir(tmp_path)
    sink = {}

    asyncio.run(_collect_login_state(
        _FakeContext({"cookies": [{**COOKIE2, "value": "new"}]}), str(path), sink
    ))
    # 采集阶段只暂存，不落盘
    assert _read(path)["cookies"][0]["value"] == "old"
    assert str(path) in sink

    asyncio.run(_flush_login_states(sink))

    saved = _read(path)
    assert saved["cookies"][0]["value"] == "new"
    assert saved["env"]["navigator"]["userAgent"] == "UA-1"


def test_scraper_swallows_capture_error(tmp_path):
    from src.scraper import _collect_login_state

    sink = {}
    asyncio.run(_collect_login_state(_FakeContext(error=RuntimeError("boom")), "a.json", sink))
    assert sink == {}


def test_scraper_swallows_flush_error(monkeypatch):
    from src.scraper import _flush_login_states
    import src.services.account_state_store as store

    def boom(path, state):
        raise RuntimeError("boom")

    monkeypatch.setattr(store, "merge_and_save", boom)
    asyncio.run(_flush_login_states({"a.json": {"cookies": [COOKIE2]}}))
