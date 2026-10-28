"""商品重新 AI 分析接口。"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services import image_cache_service as img_cache
from src.services import reanalyze_service as svc

router = APIRouter(prefix="/api/reanalyze", tags=["reanalyze"])


class ReanalyzeRequest(BaseModel):
    scope: str = Field("pending", description="pending=仅未分析 / all=全部重跑 / selected=指定条目")
    limit: Optional[int] = Field(None, ge=1, le=500, description="最多处理条数，留空表示不限")
    workers: int = Field(3, ge=1, le=8, description="并发数")
    item_ids: Optional[List[str]] = Field(None, description="scope=selected 时的商品 ID 列表")


@router.get("/status")
async def get_status():
    """查询当前/最近一次重新分析的进度。"""
    return svc.get_status()


@router.post("/start")
async def start(req: ReanalyzeRequest):
    """后台启动重新分析，立即返回，不阻塞请求。"""
    if req.scope not in (svc.SCOPE_PENDING, svc.SCOPE_ALL, svc.SCOPE_SELECTED):
        raise HTTPException(status_code=400, detail=f"不支持的 scope: {req.scope}")
    if req.scope == svc.SCOPE_SELECTED and not req.item_ids:
        raise HTTPException(status_code=400, detail="scope=selected 时必须提供 item_ids")
    if svc.get_status().get("running"):
        raise HTTPException(status_code=409, detail="已有重新分析任务在运行")

    async def _runner():
        try:
            await svc.run_analyze(
                scope=req.scope,
                limit=req.limit,
                workers=req.workers,
                only_ids=req.item_ids,
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            svc._status.update({
                "running": False,
                "message": f"重新分析异常终止: {exc}",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            })

    asyncio.create_task(_runner())
    return {"message": "已开始重新分析", "status": svc.get_status()}


@router.post("/cancel")
async def cancel():
    """请求取消正在进行的重新分析。"""
    if not svc.cancel_analyze():
        raise HTTPException(status_code=400, detail="当前没有正在进行的重新分析")
    return {"message": "已发送取消请求", "status": svc.get_status()}

@router.get("/images/stats")
async def images_stats():
    """查询商品图片缓存占用。"""
    return img_cache.get_stats()


@router.delete("/images")
async def clear_images(only_task: Optional[str] = None):
    """清理商品图片缓存（可指定只清理某个任务目录）。"""
    if svc.get_status().get("running"):
        raise HTTPException(status_code=409, detail="正在分析中，请先等待完成再清理图片")
    return img_cache.clear(only_task=only_task)
