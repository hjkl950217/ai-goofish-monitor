from src.services.prompt_defaults import ensure_default_prompts


def test_ensure_default_prompts_creates_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    created = ensure_default_prompts()

    assert "base_prompt.txt" in created
    assert "model_check_prompt.txt" in created
    target = tmp_path / "prompts" / "model_check_prompt.txt"
    assert target.exists()
    assert "{{TARGET}}" in target.read_text(encoding="utf-8")


def test_ensure_default_prompts_keeps_user_edits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    custom = prompts / "model_check_prompt.txt"
    custom.write_text("用户改过的内容", encoding="utf-8")

    created = ensure_default_prompts()

    assert "model_check_prompt.txt" not in created
    assert custom.read_text(encoding="utf-8") == "用户改过的内容"


def test_ensure_default_prompts_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    first = ensure_default_prompts()
    second = ensure_default_prompts()

    assert first
    assert second == []
