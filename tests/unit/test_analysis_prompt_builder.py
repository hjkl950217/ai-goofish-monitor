"""判断标准优先取任务字段，字段为空才回退到文件。"""
import pytest

from src.services.analysis_prompt_builder import build_analysis_prompt


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_prefers_task_criteria_over_file(tmp_path):
    base = _write(tmp_path / "base.txt", "HEAD{{CRITERIA_SECTION}}TAIL")
    criteria_file = _write(tmp_path / "criteria.txt", "FILE_CONTENT")

    prompt = build_analysis_prompt(
        {
            "ai_prompt_base_file": base,
            "ai_prompt_criteria_file": criteria_file,
            "criteria_text": "TASK_CONTENT",
        }
    )

    assert "TASK_CONTENT" in prompt
    assert "FILE_CONTENT" not in prompt


def test_falls_back_to_file_when_task_field_empty(tmp_path):
    base = _write(tmp_path / "base.txt", "HEAD{{CRITERIA_SECTION}}TAIL")
    criteria_file = _write(tmp_path / "criteria.txt", "FILE_CONTENT")

    prompt = build_analysis_prompt(
        {
            "ai_prompt_base_file": base,
            "ai_prompt_criteria_file": criteria_file,
            "criteria_text": None,
        }
    )

    assert prompt == "HEADFILE_CONTENTTAIL"


def test_raises_when_no_criteria_anywhere(tmp_path):
    base = _write(tmp_path / "base.txt", "HEAD{{CRITERIA_SECTION}}TAIL")

    with pytest.raises(RuntimeError):
        build_analysis_prompt(
            {
                "ai_prompt_base_file": base,
                "ai_prompt_criteria_file": "",
                "criteria_text": "   ",
            }
        )


def test_relative_paths_resolve_against_root(tmp_path):
    _write(tmp_path / "base.txt", "H{{CRITERIA_SECTION}}T")

    prompt = build_analysis_prompt(
        {
            "ai_prompt_base_file": "base.txt",
            "ai_prompt_criteria_file": "",
            "criteria_text": "C",
        },
        root=tmp_path,
    )

    assert prompt == "HCT"
