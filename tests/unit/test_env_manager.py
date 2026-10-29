from src.infrastructure.config.store import ConfigStore, config_store


def test_global_config_store_uses_jsonc_file():
    # 配置落在已挂载的 data/config.jsonc（测试环境里指向临时目录，文件名不变）
    assert config_store.path.name == "config.jsonc"


def test_apply_writes_to_config_file_and_reads_back(tmp_path):
    store = ConfigStore(tmp_path / "config.jsonc", tmp_path / "config.key")
    store.apply({"WEBHOOK_URL": "https://hooks.example.com/saved"})

    assert "WEBHOOK_URL" in store.raw()
    assert store.get("WEBHOOK_URL") == "https://hooks.example.com/saved"


def test_get_value_falls_back_to_runtime_when_missing_from_file(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/runtime")
    store = ConfigStore(tmp_path / "config.jsonc", tmp_path / "config.key")
    store.load()

    assert store.get("WEBHOOK_URL") == "https://hooks.example.com/runtime"


def test_file_value_wins_over_runtime_env(tmp_path, monkeypatch):
    path = tmp_path / "config.jsonc"
    path.write_text(
        '{"notification": {"WEBHOOK_URL": "https://hooks.example.com/file"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/env")

    store = ConfigStore(path, tmp_path / "config.key")
    store.load()

    assert store.get("WEBHOOK_URL") == "https://hooks.example.com/file"
