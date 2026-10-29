"""JSONC 解析、密钥加解密、配置文件读写。"""
import os

import pytest

from src.infrastructure.config import jsonc, secret_box
from src.infrastructure.config.store import ConfigStore


def _store(tmp_path) -> ConfigStore:
    return ConfigStore(tmp_path / "config.jsonc", tmp_path / "config.key")


# ---------------------------------------------------------------- JSONC


def test_jsonc_strips_comments_and_trailing_commas():
    text = """
    {
      // 模型配置
      "ai": {
        "KEY": "a//b", /* 行内注释 */
        "N": 1,
      },
    }
    """
    assert jsonc.loads(text) == {"ai": {"KEY": "a//b", "N": 1}}


def test_jsonc_keeps_hash_and_slashes_inside_strings():
    assert jsonc.loads('{"a": "http://x/*y*/", "b": "#tag"}') == {
        "a": "http://x/*y*/",
        "b": "#tag",
    }


# ---------------------------------------------------------------- 密钥


def test_sensitive_keys():
    assert secret_box.is_sensitive("OPENAI_API_KEY")
    assert secret_box.is_sensitive("TELEGRAM_BOT_TOKEN")
    assert secret_box.is_sensitive("WEB_PASSWORD")
    assert secret_box.is_sensitive("WEBHOOK_URL")
    assert not secret_box.is_sensitive("OPENAI_BASE_URL")
    assert not secret_box.is_sensitive("RUN_HEADLESS")


def test_encrypt_roundtrip(tmp_path):
    key_path = tmp_path / "config.key"
    token = secret_box.encrypt("sk-secret-123456", key_path)
    assert token.startswith(secret_box.PREFIX)
    assert secret_box.decrypt(token, key_path) == "sk-secret-123456"


def test_mask():
    assert secret_box.mask("sk-1234567890") == "sk-1****7890"
    assert secret_box.mask("short") == "****"
    assert secret_box.mask("") == ""


# ---------------------------------------------------------------- 读写


def test_store_prefers_file_over_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_NAME", "from-env")
    path = tmp_path / "config.jsonc"
    path.write_text('{"ai": {"OPENAI_MODEL_NAME": "from-file"}}', encoding="utf-8")

    store = ConfigStore(path, tmp_path / "config.key")
    store.load()

    assert os.environ["OPENAI_MODEL_NAME"] == "from-file"
    assert store.get("OPENAI_MODEL_NAME") == "from-file"


def test_apply_encrypts_sensitive_values(tmp_path):
    store = _store(tmp_path)
    store.apply({"OPENAI_API_KEY": "sk-test-123456"})

    raw = store.raw()
    assert "sk-test-123456" not in raw
    assert secret_box.PREFIX in raw

    written = jsonc.loads(raw)["ai"]["OPENAI_API_KEY"]
    assert secret_box.decrypt(written, tmp_path / "config.key") == "sk-test-123456"


def test_apply_writes_key_and_group_comments(tmp_path):
    store = _store(tmp_path)
    store.apply({"OPENAI_MODEL_NAME": "mimo"})

    raw = store.raw()
    assert "// AI 模型" in raw
    assert "// OPENAI_MODEL_NAME：" in raw
    assert jsonc.loads(raw)["ai"]["OPENAI_MODEL_NAME"] == "mimo"


def test_bootstrap_annotates_existing_file_without_comments(tmp_path):
    path = tmp_path / "config.jsonc"
    path.write_text('{"ai": {"OPENAI_MODEL_NAME": "mimo"}}', encoding="utf-8")

    store = ConfigStore(path, tmp_path / "config.key")
    assert store.bootstrap() is False
    assert "// OPENAI_MODEL_NAME：" in store.raw()
    assert jsonc.loads(store.raw())["ai"]["OPENAI_MODEL_NAME"] == "mimo"

    # 再跑一次不重复插注释
    store.bootstrap()
    assert store.raw().count("// OPENAI_MODEL_NAME：") == 1


def test_apply_ignores_unknown_keys(tmp_path):
    store = _store(tmp_path)
    store.apply({"PATH": "/hacked"})
    assert store.raw() == "" or "PATH" not in store.raw()


def test_save_raw_rejects_invalid_jsonc(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.save_raw("{ broken")
    assert not store.path.exists()


def test_bootstrap_creates_file_and_encrypts_password(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_NAME", "mimo")
    monkeypatch.setenv("WEB_PASSWORD", "pw-12345678")

    store = _store(tmp_path)
    assert store.bootstrap() is True

    raw = store.raw()
    assert "OPENAI_MODEL_NAME" in raw
    assert "pw-12345678" not in raw


def test_bootstrap_skips_when_file_exists(tmp_path):
    path = tmp_path / "config.jsonc"
    path.write_text("{}", encoding="utf-8")
    store = ConfigStore(path, tmp_path / "config.key")
    assert store.bootstrap() is False
