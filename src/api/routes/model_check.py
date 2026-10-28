"""历史商品型号校验接口。"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services import model_check_backfill_service as svc

router = APIRouter(prefix="/api/model-check", tags=["model-check"])


class ModelCheckRequest(BaseModel):
    workers: int = Field(3, ge=1, le=8, description="并发数")
    result_filename: Optional[str] = Field(None, description="只校验指定结果文件，留空表示全部")


@router.get("/status")
async def get_status():
    """查询当前/最近一次型号校验的进度。"""
    return svc.get_status()


@router.post("/start")
async def start(req: ModelCheckRequest):
    """后台启动历史校验，立即返回。"""
    if svc.get_status().get("running"):
        raise HTTPException(status_code=409, detail="已有型号校验任务在运行")

    async def _runner():
        try:
            await svc.run_check(
                workers=req.workers,
                result_filename=req.result_filename,
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            svc._status.update({
                "running": False,
                "message": f"型号校验异常终止: {exc}",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            })

    asyncio.create_task(_runner())
    return {"message": "已开始型号校验", "status": svc.get_status()}


@router.post("/cancel")
async def cancel():
    """请求取消正在进行的型号校验。"""
    if not svc.cancel_check():
        raise HTTPException(status_code=400, detail="当前没有正在进行的型号校验")
    return {"message": "已发送取消请求", "status": svc.get_status()}
