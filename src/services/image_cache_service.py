"""商品图片缓存管理。

任务图片保存在 images/task_images_<任务名>/ 下（KEEP_TASK_IMAGES 开启时保留）。
这里提供统计与清理能力，供前端按钮与命令行共用。
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List

IMAGE_SAVE_DIR = "images"
TASK_IMAGE_DIR_PREFIX = "task_images_"


def _cache_root() -> str:
    return IMAGE_SAVE_DIR


def _human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024 or unit == "GB":
            return f"{num_bytes:.1f}{unit}" if unit != "B" else f"{int(num_bytes)}B"
        num_bytes /= 1024
    return f"{num_bytes:.1f}GB"


def get_stats() -> Dict[str, Any]:
    """统计图片缓存占用情况。"""
    root = _cache_root()
    dirs: List[Dict[str, Any]] = []
    total_bytes = 0
    total_files = 0

    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not name.startswith(TASK_IMAGE_DIR_PREFIX) or not os.path.isdir(path):
                continue
            size = 0
            count = 0
            for entry in os.scandir(path):
                if entry.is_file():
                    try:
                        size += entry.stat().st_size
                        count += 1
                    except OSError:
                        continue
            dirs.append({
                "name": name,
                "task": name[len(TASK_IMAGE_DIR_PREFIX):],
                "files": count,
                "bytes": size,
                "size": _human_size(size),
            })
            total_bytes += size
            total_files += count

    return {
        "root": root,
        "exists": os.path.isdir(root),
        "task_count": len(dirs),
        "file_count": total_files,
        "total_bytes": total_bytes,
        "total_size": _human_size(total_bytes),
        "dirs": dirs,
    }


def clear(only_task: str | None = None) -> Dict[str, Any]:
    """清理图片缓存；only_task 指定时只清理该任务目录。"""
    root = _cache_root()
    before = get_stats()
    removed: List[str] = []
    freed = 0
    errors: List[str] = []

    if not os.path.isdir(root):
        return {"removed": removed, "freed_bytes": 0, "freed_size": "0B", "errors": errors}

    targets = []
    for name in sorted(os.listdir(root)):
        if not name.startswith(TASK_IMAGE_DIR_PREFIX):
            continue
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        if only_task and name[len(TASK_IMAGE_DIR_PREFIX):] != only_task:
            continue
        targets.append((name, path))

    for name, path in targets:
        # 双重保险：只删除 images/ 下以 task_images_ 开头的目录
        if not os.path.abspath(path).startswith(os.path.abspath(root) + os.sep) \
                or not name.startswith(TASK_IMAGE_DIR_PREFIX):
            errors.append(f"跳过非法路径: {path}")
            continue
        try:
            freed += sum(
                entry.stat().st_size
                for entry in os.scandir(path)
                if entry.is_file()
            )
            shutil.rmtree(path)
            removed.append(name)
        except OSError as exc:
            errors.append(f"{name}: {exc}")

    after = get_stats()
    return {
        "removed": removed,
        "freed_bytes": freed,
        "freed_size": _human_size(freed),
        "remaining_size": after["total_size"],
        "before_size": before["total_size"],
        "errors": errors,
    }