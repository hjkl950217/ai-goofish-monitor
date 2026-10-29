"""统一的配置存储。

唯一的持久化文件是 data/config.jsonc（JSONC，支持注释）。
读取顺序：配置文件 > 进程环境变量 > 代码默认值。

加载时把配置文件里的值写进 os.environ（覆盖同名环境变量），
因此现有的 os.getenv 调用点自动变成「配置文件优先」，不需要逐个改。
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from src.infrastructure.config import jsonc, secret_box

DEFAULT_PATH = "data/config.jsonc"
DEFAULT_KEY_PATH = "data/.config.key"

# 配置分组只影响生成出来的文件结构与前端展示，键名沿用环境变量名
CONFIG_GROUPS: dict[str, tuple[str, ...]] = {
    "ai": (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL_NAME",
        "PROXY_URL",
        "AI_DEBUG_MODE",
        "ENABLE_THINKING",
        "ENABLE_RESPONSE_FORMAT",
        "SKIP_AI_ANALYSIS",
        "AI_ANALYSIS_CONCURRENCY",
    ),
    "model_check": (
        "MODEL_CHECK_ENABLED",
        "MODEL_CHECK_BASE_URL",
        "MODEL_CHECK_API_KEY",
        "MODEL_CHECK_MODEL_NAME",
        "MODEL_CHECK_PROXY_URL",
        "MODEL_CHECK_PREFILTER_REGEX",
    ),
    "web": ("SERVER_PORT", "WEB_USERNAME", "WEB_PASSWORD"),
    "crawler": (
        "RUN_HEADLESS",
        "LOGIN_IS_EDGE",
        "KEEP_TASK_IMAGES",
        "REFRESH_TRACKED_ITEMS",
        "PCURL_TO_MOBILE",
        "IMAGE_DOWNLOAD_CONCURRENCY",
        "SELLER_PROFILE_CACHE_TTL",
    ),
    "notification": (
        "NTFY_TOPIC_URL",
        "PUSHPLUS_TOKEN",
        "PUSHPLUS_TOPIC",
        "GOTIFY_URL",
        "GOTIFY_TOKEN",
        "BARK_URL",
        "WX_BOT_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_API_BASE_URL",
        "WEBHOOK_URL",
        "WEBHOOK_METHOD",
        "WEBHOOK_CONTENT_TYPE",
        "WEBHOOK_HEADERS",
        "WEBHOOK_QUERY_PARAMETERS",
        "WEBHOOK_BODY",
        "NOTIFICATION_DISABLED_CHANNELS",
    ),
    "account_rotation": (
        "ACCOUNT_ROTATION_ENABLED",
        "ACCOUNT_ROTATION_MODE",
        "ACCOUNT_ROTATION_RETRY_LIMIT",
        "ACCOUNT_ROTATION_BLACKLIST_TTL",
        "ACCOUNT_BLACKLIST_TTL",
    ),
    "proxy_rotation": (
        "PROXY_ROTATION_ENABLED",
        "PROXY_ROTATION_MODE",
        "PROXY_ROTATION_RETRY_LIMIT",
        "PROXY_ROTATION_BLACKLIST_TTL",
        "PROXY_BLACKLIST_TTL",
        "PROXY_POOL",
    ),
    "failure_guard": (
        "TASK_FAILURE_THRESHOLD",
        "TASK_FAILURE_PAUSE_SECONDS",
        "TASK_FAILURE_GUARD_PATH",
        "TASK_FAILURE_TZ",
    ),
    "paths": (
        "ACCOUNT_STATE_DIR",
        "APP_DATABASE_FILE",
    ),
    "logs_and_trace": (
        "TASK_LOG_RETENTION_DAYS",
        "AI_LOG_RETENTION_DAYS",
        "AGM_BROWSER_TRACE",
        "AGM_TRACE_DIR",
        "AGM_TRACE_MAX_MB",
        "AGM_DEBUG_CAPTURE",
    ),
}

KNOWN_KEYS: tuple[str, ...] = tuple(key for keys in CONFIG_GROUPS.values() for key in keys)


def _to_env(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class ConfigStore:
    """配置文件读写与进程环境同步。"""

    def __init__(self, path: str | Path = DEFAULT_PATH, key_path: str | Path = DEFAULT_KEY_PATH):
        self.path = Path(path)
        self.key_path = Path(key_path)
        self._values: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- 读取

    def load(self, *, apply_to_environ: bool = True) -> None:
        data = self._read_file()
        flat: dict[str, Any] = {}
        for group in data.values():
            if isinstance(group, dict):
                flat.update(group)
        self._values = flat
        if apply_to_environ:
            for key, value in flat.items():
                plain = self._plain(key, value)
                if plain in (None, ""):
                    # 空值也写进环境，避免部署时残留的旧环境变量盖住「清空」的意图
                    if key in os.environ:
                        os.environ[key] = ""
                    continue
                os.environ[key] = _to_env(plain)

    def _plain(self, key: str, value: Any) -> Any:
        """密文在注入环境与对外读取时都还原成明文。"""
        if not secret_box.is_encrypted(value):
            return value
        try:
            return secret_box.decrypt(value, self.key_path)
        except Exception as exc:
            print(f"[配置] {key} 解密失败，按未配置处理：{exc}")
            return None

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._values:
            value = self._plain(key, self._values[key])
            return default if value in (None, "") else value
        env_value = os.getenv(key)
        return default if env_value in (None, "") else env_value

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key)
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def as_mapping(self) -> dict[str, Any]:
        return dict(self._values)

    def plain_mapping(self) -> dict[str, Any]:
        """返回解密后的键值，供内部读取；敏感值不要直接回给前端。"""
        return {key: self._plain(key, value) for key, value in self._values.items()}

    def reset(self) -> None:
        """清空内存缓存，测试之间互不影响。"""
        self._values = {}

    def masked(self) -> dict[str, str]:
        """返回脱敏后的配置，用于前端展示；不返回明文。"""
        result: dict[str, str] = {}
        for key, value in self._values.items():
            if not secret_box.is_sensitive(key) or value in (None, ""):
                continue
            plain = value
            try:
                plain = secret_box.decrypt(value, self.key_path) if secret_box.is_encrypted(value) else str(value)
            except Exception:
                plain = ""
            result[key] = secret_box.mask(plain)
        return result

    # ---------------------------------------------------------------- 写入

    def apply(self, updates: dict[str, Any]) -> None:
        """按扁平键写回文件并重载。

        会重排文件（手写注释不保留）；需要保留注释时用 save_raw 直接改原文。
        """
        with self._lock:
            data = self._read_file()
            for key, value in updates.items():
                if key not in KNOWN_KEYS:
                    continue
                group = _group_of(key)
                bucket = data.setdefault(group, {})
                if not isinstance(bucket, dict):
                    bucket = {}
                    data[group] = bucket
                if value is None or value == "":
                    bucket.pop(key, None)
                    continue
                if secret_box.is_sensitive(key) and not secret_box.is_encrypted(value):
                    value = secret_box.encrypt(str(value), self.key_path)
                bucket[key] = value
            self._write_file(data)
        self.load()

    def save_raw(self, text: str) -> None:
        """保存配置文件原文；语法错误抛 ValueError，不落盘。"""
        try:
            jsonc.loads(text)
        except ValueError as exc:
            raise ValueError(f"配置不是合法的 JSONC：{exc}") from exc
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
        self.load()

    def raw(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def bootstrap(self, env_file: Path | None = None) -> bool:
        """文件不存在时，用 data/.env 与当前环境变量生成一份。返回是否新建。"""
        if self.path.exists():
            return False
        data: dict[str, dict[str, Any]] = {}
        for key in KNOWN_KEYS:
            value = os.getenv(key)
            if value in (None, ""):
                continue
            if secret_box.is_sensitive(key):
                value = secret_box.encrypt(value, self.key_path)
            data.setdefault(_group_of(key), {})[key] = value
        if not data:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_file(data)
        return True

    # ---------------------------------------------------------------- 内部

    def _read_file(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        text = self.path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        try:
            data = jsonc.loads(text)
        except ValueError as exc:
            print(f"[配置] {self.path} 解析失败，回退到环境变量：{exc}")
            return {}
        return data if isinstance(data, dict) else {}

    def _write_file(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(jsonc.dumps(_ordered(data)), encoding="utf-8")
        os.replace(tmp, self.path)


def _group_of(key: str) -> str:
    for group, keys in CONFIG_GROUPS.items():
        if key in keys:
            return group
    return "other"


def _ordered(data: dict[str, Any]) -> dict[str, Any]:
    """按 CONFIG_GROUPS 的顺序输出，未知分组排在最后。"""
    ordered: dict[str, Any] = {}
    for group in CONFIG_GROUPS:
        if group in data:
            ordered[group] = data[group]
    for group, value in data.items():
        if group not in ordered:
            ordered[group] = value
    return ordered


config_store = ConfigStore(
    os.getenv("AGM_CONFIG_FILE", DEFAULT_PATH),
    os.getenv("AGM_CONFIG_KEY_FILE", DEFAULT_KEY_PATH),
)
