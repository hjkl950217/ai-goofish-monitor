"""运维配置：调试采集、浏览器采样与任务运行选项。

采集开关只影响排查用的数据落盘；运行选项影响任务本身的行为。
两类都在下一个任务启动时生效（任务跑在独立子进程里，子进程启动会重读 data/.env）。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.config.env_manager import env_manager
from src.services import browser_trace_service

router = APIRouter(prefix="/api/ops", tags=["ops"])

DEBUG_CAPTURE_KEY = "AGM_DEBUG_CAPTURE"
TRACE_KEY = "AGM_BROWSER_TRACE"
TRACE_DIR_KEY = "AGM_TRACE_DIR"

# 布尔型运行开关及默认值，与代码里的读取默认值保持一致
RUNTIME_BOOL_KEYS = {
    "KEEP_TASK_IMAGES": True,
    "REFRESH_TRACKED_ITEMS": True,
    "AI_DEBUG_MODE": False,
    "ENABLE_THINKING": False,
    "ENABLE_RESPONSE_FORMAT": True,
}
# 整数型运行开关及默认值
RUNTIME_INT_KEYS = {
    "TASK_FAILURE_THRESHOLD": 3,
    "TASK_FAILURE_PAUSE_SECONDS": 86400,
    "TASK_LOG_RETENTION_DAYS": 7,
    "AI_LOG_RETENTION_DAYS": 1,
    "AGM_TRACE_MAX_MB": 200,
}


class OpsConfig(BaseModel):
    AGM_DEBUG_CAPTURE: Optional[str] = None
    AGM_BROWSER_TRACE: Optional[str] = None
    AGM_TRACE_DIR: Optional[str] = None
    KEEP_TASK_IMAGES: Optional[bool] = None
    REFRESH_TRACKED_ITEMS: Optional[bool] = None
    AI_DEBUG_MODE: Optional[bool] = None
    ENABLE_THINKING: Optional[bool] = None
    ENABLE_RESPONSE_FORMAT: Optional[bool] = None
    TASK_FAILURE_THRESHOLD: Optional[int] = None
    TASK_FAILURE_PAUSE_SECONDS: Optional[int] = None
    TASK_LOG_RETENTION_DAYS: Optional[int] = None
    AI_LOG_RETENTION_DAYS: Optional[int] = None
    AGM_TRACE_MAX_MB: Optional[int] = None


def _current_trace_dir() -> str:
    value = (env_manager.get_value(TRACE_DIR_KEY, "") or "").strip()
    return value or browser_trace_service.DEFAULT_TRACE_DIR


def _bool_value(key: str, default: bool) -> bool:
    raw = env_manager.get_value(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_value(key: str, default: int) -> int:
    raw = env_manager.get_value(key)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


@router.get("/config")
async def get_ops_config():
    config = {
        DEBUG_CAPTURE_KEY: (env_manager.get_value(DEBUG_CAPTURE_KEY, "") or "").strip(),
        TRACE_KEY: (env_manager.get_value(TRACE_KEY, "") or "").strip().lower(),
        TRACE_DIR_KEY: _current_trace_dir(),
    }
    config.update({key: _bool_value(key, default) for key, default in RUNTIME_BOOL_KEYS.items()})
    config.update({key: _int_value(key, default) for key, default in RUNTIME_INT_KEYS.items()})
    return config


@router.put("/config")
async def update_ops_config(payload: OpsConfig):
    updates: dict[str, str] = {}

    if payload.AGM_DEBUG_CAPTURE is not None:
        updates[DEBUG_CAPTURE_KEY] = payload.AGM_DEBUG_CAPTURE.strip()
    if payload.AGM_BROWSER_TRACE is not None:
        updates[TRACE_KEY] = str(payload.AGM_BROWSER_TRACE).strip().lower()
    if payload.AGM_TRACE_DIR is not None:
        trace_dir = payload.AGM_TRACE_DIR.strip() or browser_trace_service.DEFAULT_TRACE_DIR
        if not trace_dir.startswith("/"):
            raise HTTPException(status_code=400, detail="采样目录必须是绝对路径")
        updates[TRACE_DIR_KEY] = trace_dir

    for key in RUNTIME_BOOL_KEYS:
        value = getattr(payload, key)
        if value is not None:
            updates[key] = "true" if value else "false"
    for key in RUNTIME_INT_KEYS:
        value = getattr(payload, key)
        if value is None:
            continue
        if value < 0:
            raise HTTPException(status_code=400, detail=f"{key} 不能是负数")
        updates[key] = str(value)

    if updates and not env_manager.update_values(updates):
        raise HTTPException(status_code=500, detail="保存运维配置失败")
    return {"message": "运维配置已保存，对下一个任务生效"}


@router.get("/traces")
async def list_traces():
    return browser_trace_service.list_traces(_current_trace_dir())
