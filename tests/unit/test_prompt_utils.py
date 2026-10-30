import asyncio

import pytest

import src.prompt_utils as prompt_utils
from src.services.ai_response_parser import EmptyAIResponseError


def test_generate_criteria_closes_ai_client_after_success(monkeypatch, tmp_path):
    close_state = {"closed": False}
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            return "generated criteria"

        async def close(self):
            close_state["closed"] = True

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    result = asyncio.run(
        prompt_utils.generate_criteria("need a gpu", str(reference_file))
    )

    assert result == "generated criteria"
    assert close_state["closed"] is True


def test_generate_criteria_drops_think_blocks_and_raises_output_limit(monkeypatch, tmp_path):
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")
    captured = {}

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **kwargs):
            captured.update(kwargs)
            return "<think>先分析需求</think>\n\n一票否决：电池健康度不足"

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    result = asyncio.run(
        prompt_utils.generate_criteria("need a watch", str(reference_file))
    )

    assert result == "一票否决：电池健康度不足"
    assert captured["max_output_tokens"] == prompt_utils.CRITERIA_MAX_OUTPUT_TOKENS
    assert captured["max_output_tokens"] > 800


def test_generate_criteria_rejects_truncated_think_block(monkeypatch, tmp_path):
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            return "<think>输出到这里被截断"

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    with pytest.raises(RuntimeError, match="思考过程占满了输出长度"):
        asyncio.run(prompt_utils.generate_criteria("need a watch", str(reference_file)))


def test_generate_criteria_rejects_truncated_criteria(monkeypatch, tmp_path):
    """加粗没闭合说明输出被截断，不能把半截标准存下来。"""
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            return "**一票否决**：电池健康度不足\n\n2. **电池配置：不带电池或电池已报废"

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    with pytest.raises(RuntimeError, match="疑似被截断"):
        asyncio.run(prompt_utils.generate_criteria("need a bike", str(reference_file)))


def test_generate_criteria_includes_target_keyword(monkeypatch, tmp_path):
    """搜索关键词要进 meta prompt，否则生成的标准锁不住品牌型号。"""
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")
    captured = {}

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, messages, **_kwargs):
            captured["prompt"] = messages[0]["content"]
            return "**分析标准** 完整内容。"

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    asyncio.run(
        prompt_utils.generate_criteria(
            "需要一台电动车",
            str(reference_file),
            target_keyword="九号n1 90",
        )
    )

    assert "九号n1 90" in captured["prompt"]


def test_generate_criteria_closes_ai_client_after_ai_failure(monkeypatch, tmp_path):
    close_state = {"closed": False}
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            raise EmptyAIResponseError("AI响应内容为空。")

        async def close(self):
            close_state["closed"] = True

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    with pytest.raises(EmptyAIResponseError, match="AI响应内容为空"):
        asyncio.run(prompt_utils.generate_criteria("need a gpu", str(reference_file)))

    assert close_state["closed"] is True
