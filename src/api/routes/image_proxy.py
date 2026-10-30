"""图片代理接口：结果卡片用它取缩略图。"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from src.services import image_proxy_service as svc

router = APIRouter(prefix="/api/images", tags=["images"])

# 一个进程最多同时拉 4 张，避免一屏 15 张图把 CDN 和出口带宽同时打满
_fetch_sem = asyncio.Semaphore(4)


@router.get("/thumb")
async def get_thumbnail(
    src: str,
    w: int = Query(svc.DEFAULT_WIDTH, ge=64, le=svc.MAX_WIDTH),
):
    if not svc.is_allowed(src):
        raise HTTPException(status_code=404, detail="不允许的图片地址")
    path = svc.cache_path(src, w)
    if not os.path.isfile(path):
        async with _fetch_sem:
            # 拿到锁后再确认一次，避免同一张图被并发拉两遍
            if not os.path.isfile(path):
                path = await run_in_threadpool(svc.ensure_cached, src, w)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=502, detail="图片下载失败")
    # FileResponse 自带 ETag/Last-Modified，浏览器第二次直接用 304
    return FileResponse(
        path,
        media_type=svc.media_type(path),
        headers={"Cache-Control": "public, max-age=604800"},
    )
