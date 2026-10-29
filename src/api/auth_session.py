"""Web 会话 Cookie。

用 HMAC 签名的自包含 token，不引入额外依赖；改 WEB_PASSWORD 会立即使旧会话失效。
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Mapping, Optional

COOKIE_NAME = "agm_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600


def _secret(password: str) -> bytes:
    return hashlib.sha256(f"agm-session:{password}".encode("utf-8")).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(username: str, password: str, now: Optional[int] = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = {"u": username, "exp": issued + SESSION_TTL_SECONDS}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(_secret(password), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_token(
    token: Optional[str],
    username: str,
    password: str,
    now: Optional[int] = None,
) -> bool:
    if not token or "." not in token:
        return False
    encoded, signature = token.split(".", 1)
    expected = _b64encode(hmac.new(_secret(password), encoded.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        payload = json.loads(_b64decode(encoded))
    except (ValueError, json.JSONDecodeError):
        return False
    return payload.get("u") == username and int(payload.get("exp", 0)) > int(
        now if now is not None else time.time()
    )


def is_authenticated(cookies: Mapping[str, str]) -> bool:
    from src.infrastructure.config.settings import settings

    return verify_token(
        cookies.get(COOKIE_NAME),
        settings.web_username,
        settings.web_password,
    )
