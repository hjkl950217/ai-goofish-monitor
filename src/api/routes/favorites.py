"""
收藏相关 API：查看/添加/取消结果商品的闲鱼收藏。
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.favorite_service import list_favorites, set_favorite

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteAction(BaseModel):
    action: Literal["add", "remove"]
    link: Optional[str] = None
    title: Optional[str] = None


@router.get("")
async def get_favorites():
    return {"favorites": list_favorites()}


@router.post("/{item_id}")
async def update_favorite(item_id: str, payload: FavoriteAction):
    try:
        favorited = await set_favorite(
            item_id,
            action=payload.action,
            link=payload.link,
            title=payload.title,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"同步闲鱼收藏失败: {exc}")
    return {"item_id": item_id, "favorited": favorited}