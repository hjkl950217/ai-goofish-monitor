from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from src.services import image_proxy_service as svc


def _png(width=800, height=600):
    buf = BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_only_taobao_hosts_allowed():
    assert svc.is_allowed("https://img.alicdn.com/a.jpg")
    assert svc.is_allowed("http://gw.alicdn.com/a.webp")
    assert svc.is_allowed("https://alicdn.com/a.webp")
    assert not svc.is_allowed("https://evil.com/a.jpg")
    assert not svc.is_allowed("https://img.alicdn.com.evil.com/a.jpg")
    assert not svc.is_allowed("file:///etc/passwd")
    assert not svc.is_allowed("")


def test_cache_path_is_stable_and_width_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "CACHE_DIR", str(tmp_path))
    first = svc.cache_path("https://img.alicdn.com/a.jpg", 480)
    assert first == svc.cache_path("https://img.alicdn.com/a.jpg", 480)
    assert first.startswith(str(tmp_path))
    assert svc.cache_path("https://img.alicdn.com/a.jpg", 240) != first


def test_thumbnail_scales_down_to_width():
    data = svc.build_thumbnail(_png(1200, 600), 300)
    with Image.open(BytesIO(data)) as img:
        assert (img.width, img.height) == (300, 150)
    assert data[:4] == b"RIFF"


def test_thumbnail_keeps_images_already_smaller():
    data = svc.build_thumbnail(_png(100, 80), 480)
    with Image.open(BytesIO(data)) as img:
        assert img.width == 100


def test_thumbnail_returns_none_for_garbage():
    assert svc.build_thumbnail(b"not an image", 300) is None


def test_ensure_cached_downloads_once(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "CACHE_DIR", str(tmp_path))
    calls = []

    class Response:
        content = _png(800, 400)

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(svc, "requests", SimpleNamespace(get=fake_get))

    first = svc.ensure_cached("https://img.alicdn.com/b.jpg", 240)
    second = svc.ensure_cached("https://img.alicdn.com/b.jpg", 240)

    assert first == second
    assert calls == ["https://img.alicdn.com/b.jpg"]
    with Image.open(first) as img:
        assert img.width == 240


def test_ensure_cached_refuses_foreign_host(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "CACHE_DIR", str(tmp_path))
    assert svc.ensure_cached("https://evil.com/a.jpg", 240) is None


def test_media_type_sniffs_header(tmp_path):
    path = tmp_path / "a.img"
    path.write_bytes(_png(10, 10))
    assert svc.media_type(str(path)) == "image/png"
    path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 20)
    assert svc.media_type(str(path)) == "image/jpeg"
    path.write_bytes(b"RIFF" + b"0" * 12 + b"WEBP")
    assert svc.media_type(str(path)) == "image/webp"
