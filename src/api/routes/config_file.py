"""配置文件读写：给设置页的「配置文件」tab 用。

保存成功后立即重新加载配置；直接改磁盘上的文件则要重启容器才生效。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.config.settings import reload_settings
from src.infrastructure.config.store import config_store

router = APIRouter(prefix="/api/config", tags=["config"])


class RawConfigUpdate(BaseModel):
    content: str


@router.get("/raw")
async def get_raw_config():
    return {"path": str(config_store.path), "content": config_store.raw()}


@router.put("/raw")
async def save_raw_config(payload: RawConfigUpdate):
    try:
        config_store.save_raw(payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    reload_settings()
    return {"message": "已保存并重新加载配置"}


@router.get("/masked")
async def get_masked_config():
    """敏感项只返回掩码，其余原样，用于页面预览。"""
    return {
        "path": str(config_store.path),
        "values": config_store.masked(),
    }
