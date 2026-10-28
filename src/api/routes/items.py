"""商品详情接口：完整记录 + 本地已下载图片。"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.services import item_detail_service as svc

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("/{item_id}")
async def get_item(item_id: str) -> Dict[str, Any]:
    record = svc.get_item(item_id)
    if not record:
        raise HTTPException(status_code=404, detail="商品不存在或已被删除")
    return record


@router.get("/{item_id}/images")
async def list_images(item_id: str) -> Dict[str, Any]:
    images: List[Dict[str, Any]] = svc.list_item_images(item_id)
    return {"item_id": item_id, "images": images, "count": len(images)}


@router.get("/{item_id}/images/{name}")
async def get_image(item_id: str, name: str):
    path = svc.resolve_image_path(item_id, name)
    if not path:
        raise HTTPException(status_code=404, detail="图片不存在或已被清理")
    return FileResponse(path)