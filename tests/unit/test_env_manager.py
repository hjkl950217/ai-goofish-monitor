from pathlib import Path

from src.infrastructure.config.env_manager import EnvManager, env_manager


def test_get_value_prefers_env_file_when_key_present(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("WEBHOOK_URL=https://hooks.example.com/new\n", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/old")

    manager = EnvManager(str(env_file))

    assert manager.get_value("WEBHOOK_URL") == "https://hooks.example.com/new"


def test_get_value_falls_back_to_runtime_when_key_missing_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/runtime")

    manager = EnvManager(str(env_file))

    assert manager.get_value("WEBHOOK_URL") == "https://hooks.example.com/runtime"


def test_global_env_manager_persists_to_data_env():
    # 站内保存的配置必须落在已挂载的 data/.env，容器重建才不丢
    assert env_manager.env_file == Path("data/.env")


def test_update_values_writes_to_env_file_and_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    manager = EnvManager(str(tmp_path / "data" / ".env"))

    assert manager.update_values({"WEBHOOK_URL": "https://hooks.example.com/saved"}) is True
    saved = (tmp_path / "data" / ".env").read_text(encoding="utf-8")
    assert "WEBHOOK_URL=https://hooks.example.com/saved" in saved
    assert manager.get_value("WEBHOOK_URL") == "https://hooks.example.com/saved"
