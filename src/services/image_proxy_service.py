"""图片代理：把闲鱼 CDN 图按需拉下来，缩成缩略图缓存到本地再发给前端。

前端直连 CDN 有三个问题：换域名/加防盗链就全挂、原图几 MB 解码慢、没法统一限流。
这里只做一件最小的事：白名单域名 + 定宽缩略图 + 磁盘缓存，URL 由后端生成，前端不用改。
"""
from __future__ import annotations

import hashlib
import os
from io import BytesIO
from typing import Optional
from urllib.parse import quote, urlparse

import requests
from PIL import Image

from src.config import IMAGE_DOWNLOAD_HEADERS

CACHE_DIR = os.path.join("images", "result_cache")
DEFAULT_WIDTH = 480
MAX_WIDTH = 1200
REQUEST_TIMEOUT = 20

# 只放行闲鱼/淘宝的图片域名，避免被当成任意 URL 代理（SSRF）
ALLOWED_HOSTS = ("alicdn.com", "taobao.com", "tmall.com", "goofish.com", "aliyuncs.com")


def proxy_url(src: str, width: int = DEFAULT_WIDTH) -> str:
    return f"/api/images/thumb?src={quote(src, safe='')}&w={width}"


def is_allowed(src: str) -> bool:
    parsed = urlparse(src or "")
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host == name or host.endswith("." + name) for name in ALLOWED_HOSTS)


def cache_path(src: str, width: int) -> str:
    digest = hashlib.sha1(f"{src}|{width}".encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.img")


def build_thumbnail(raw: bytes, width: int) -> Optional[bytes]:
    """按宽缩放到 width，转 webp；图片解不开时返回 None。"""
    try:
        with Image.open(BytesIO(raw)) as img:
            img = img.convert("RGB")
            if img.width > width:
                height = max(1, round(img.height * width / img.width))
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, "WEBP", quality=78, method=4)
            return buf.getvalue()
    except Exception:  # noqa: BLE001 - 坏图/未支持的格式，交给调用方兜底
        return None


def media_type(path: str) -> str:
    """按文件头判断类型：正常是 webp，Pillow 处理不了时会原样存 jpg/png。"""
    with open(path, "rb") as f:
        head = f.read(16)
    if head[:4] == b"RIFF":
        return "image/webp"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/octet-stream"


def ensure_cached(src: str, width: int) -> Optional[str]:
    """返回缓存文件路径；没有就下载并生成缩略图。失败返回 None。"""
    path = cache_path(src, width)
    if os.path.isfile(path):
        return path
    if not is_allowed(src):
        return None
    try:
        resp = requests.get(src, headers=IMAGE_DOWNLOAD_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    body = build_thumbnail(resp.content, width) or resp.content
    os.makedirs(CACHE_DIR, exist_ok=True)
    # 先写临时文件再改名，两个请求同时拉同一张时不会读到半个文件
    tmp = f"{path}.{os.getpid()}.{id(resp)}.tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, path)
    return path
