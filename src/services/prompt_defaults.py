"""内置提示词的兜底副本。

prompts/ 在 docker-compose 里是挂载目录，宿主的空目录会盖掉镜像里的内容。
所以镜像内置一份在 src/prompt_defaults/，运行时按需复制过去。
已存在的文件不覆盖，用户改过的内容保留。
"""

from __future__ import annotations

import shutil
from pathlib import Path

DEFAULTS_DIR = Path(__file__).resolve().parent.parent / "prompt_defaults"
PROMPTS_DIR = Path("prompts")

DEFAULT_PROMPTS = (
    "base_prompt.txt",
    "example_criteria.txt",
    "macbook_criteria.txt",
    "model_check_prompt.txt",
)


def ensure_default_prompts() -> list[str]:
    """把缺失的内置提示词补到 prompts/，返回本次补出来的文件名。"""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name in DEFAULT_PROMPTS:
        source = DEFAULTS_DIR / name
        if not source.exists():
            continue
        target = PROMPTS_DIR / name
        if target.exists():
            continue
        shutil.copyfile(source, target)
        created.append(name)
    return created
