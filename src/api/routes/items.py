"""商品详情接口：完整记录 + 本地已下载图片。"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.services import item_detail_service as svc
from src.services import item_manual_refresh_service as refresh_svc

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


@router.post("/{item_id}/refresh")
async def refresh_item(item_id: str, result_filename: str | None = None) -> Dict[str, Any]:
    """手动拉一次详情页最新内容（标题、描述、价格、图片）。"""
    try:
        record = await refresh_svc.refresh_item(item_id, result_filename)
    except refresh_svc.ItemNotFound:
        raise HTTPException(status_code=404, detail="结果里没有这个商品")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"获取最新信息失败：{exc}")
    return record


@router.get("/{item_id}/images/{name}")
async def get_image(item_id: str, name: str):
    path = svc.resolve_image_path(item_id, name)
    if not path:
        raise HTTPException(status_code=404, detail="图片不存在或已被清理")
    return FileResponse(path)