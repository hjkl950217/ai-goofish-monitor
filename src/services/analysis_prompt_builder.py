"""把 base_prompt 与任务判断标准拼成最终 prompt。

优先级：任务记录里的 criteria_text > ai_prompt_criteria_file 指向的文件。
迁移前创建的任务没有 criteria_text，继续读文件，行为不变。
"""
from pathlib import Path
from typing import Any, Mapping


def _resolve(path: str, base_dir: Path) -> Path:
    target = Path(path)
    return target if target.is_absolute() else base_dir / target


def build_analysis_prompt(
    task: Mapping[str, Any],
    *,
    root: str | Path | None = None,
) -> str:
    data = dict(task)
    base_dir = Path(root) if root is not None else Path.cwd()

    base_prompt = _resolve(str(data["ai_prompt_base_file"]), base_dir).read_text(encoding="utf-8")

    criteria = str(data.get("criteria_text") or "").strip()
    if not criteria:
        criteria_file = str(data.get("ai_prompt_criteria_file") or "")
        if criteria_file:
            criteria = _resolve(criteria_file, base_dir).read_text(encoding="utf-8")

    if not criteria.strip():
        raise RuntimeError("任务缺少判断标准：criteria_text 与 criteria 文件都为空")

    return base_prompt.replace("{{CRITERIA_SECTION}}", criteria)
