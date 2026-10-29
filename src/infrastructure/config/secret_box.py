"""配置文件里的密钥字段加解密。

磁盘上以 ENC[v1]: 开头的值视为密文，其余按明文处理，两者靠前缀区分。
密钥文件默认 data/.config.key，首次加密时自动生成。
"""
from __future__ import annotations

import os
from pathlib import Path

PREFIX = "ENC[v1]:"

# 字段名匹配这些规则就加密；显式列出的 URL 里带凭据，也算
_SENSITIVE_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
_SENSITIVE_EXACT = {
    "NTFY_TOPIC_URL",
    "BARK_URL",
    "WX_BOT_URL",
    "WEBHOOK_URL",
    "WEBHOOK_HEADERS",
}


def is_encrypted(value: object) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def is_sensitive(key: str) -> bool:
    upper = key.upper()
    if upper in _SENSITIVE_EXACT:
        return True
    return any(upper.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)


def _read_key(key_path: Path) -> bytes | None:
    if not key_path.exists():
        return None
    raw = key_path.read_text(encoding="utf-8").strip()
    return raw.encode() if raw else None


def ensure_key(key_path: Path) -> bytes:
    existing = _read_key(key_path)
    if existing:
        return existing
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(key.decode(), encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


def encrypt(value: str, key_path: Path) -> str:
    from cryptography.fernet import Fernet

    token = Fernet(ensure_key(key_path)).encrypt(value.encode())
    return PREFIX + token.decode()


def decrypt(value: str, key_path: Path) -> str:
    if not is_encrypted(value):
        return value
    from cryptography.fernet import Fernet

    key = _read_key(key_path)
    if key is None:
        raise RuntimeError(f"缺少密钥文件 {key_path}，无法解密配置项")
    return Fernet(key).decrypt(value[len(PREFIX):].encode()).decode()


def mask(value: str) -> str:
    """返回给前端的脱敏值：前 4 + **** + 后 4。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
