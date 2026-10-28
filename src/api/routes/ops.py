"""运维配置：调试采集与浏览器采样的开关。

这些开关只影响排查用的数据落盘，不影响正常抓取。改完对下一个任务生效。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.config.env_manager import env_manager
from src.services import browser_trace_service

router = APIRouter(prefix="/api/ops", tags=["ops"])

DEBUG_CAPTURE_KEY = "AGM_DEBUG_CAPTURE"
TRACE_KEY = "AGM_BROWSER_TRACE"
TRACE_DIR_KEY = "AGM_TRACE_DIR"


class OpsConfig(BaseModel):
    AGM_DEBUG_CAPTURE: str = ""
    AGM_BROWSER_TRACE: str = "false"
    AGM_TRACE_DIR: str = browser_trace_service.DEFAULT_TRACE_DIR


def _current_trace_dir() -> str:
    value = (env_manager.get_value(TRACE_DIR_KEY, "") or "").strip()
    return value or browser_trace_service.DEFAULT_TRACE_DIR


@router.get("/config")
async def get_ops_config():
    return {
        DEBUG_CAPTURE_KEY: (env_manager.get_value(DEBUG_CAPTURE_KEY, "") or "").strip(),
        TRACE_KEY: (env_manager.get_value(TRACE_KEY, "") or "").strip().lower(),
        TRACE_DIR_KEY: _current_trace_dir(),
    }


@router.put("/config")
async def update_ops_config(payload: OpsConfig):
    trace_dir = payload.AGM_TRACE_DIR.strip() or browser_trace_service.DEFAULT_TRACE_DIR
    if not trace_dir.startswith("/"):
        raise HTTPException(status_code=400, detail="采样目录必须是绝对路径")
    updates = {
        DEBUG_CAPTURE_KEY: payload.AGM_DEBUG_CAPTURE.strip(),
        TRACE_KEY: str(payload.AGM_BROWSER_TRACE).strip().lower(),
        TRACE_DIR_KEY: trace_dir,
    }
    if not env_manager.update_values(updates):
        raise HTTPException(status_code=500, detail="保存运维配置失败")
    return {"message": "运维配置已保存，对下一个任务生效"}


@router.get("/traces")
async def list_traces():
    return browser_trace_service.list_traces(_current_trace_dir())
