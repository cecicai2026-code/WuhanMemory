"""照片缩略图接口：GET /media/thumbs/{宽度}/{photos 或 photos-placeholder}/{景点 id}/{文件名}（见 app/services/thumbnails.py）。

公开模式下占位照片不对外（app/core/site_policy.py），它们的缩略图也一样返回 404。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.pois import DataDir
from app.core.config import settings
from app.core.site_policy import Policy
from app.services.thumbnails import thumbnail

router = APIRouter(prefix="/media/thumbs", tags=["media"])


def get_thumb_cache_dir() -> Path:
    return settings.data_dir / "thumbs"


CacheDir = Annotated[Path, Depends(get_thumb_cache_dir)]


@router.get("/{width}/{collection}/{poi_id}/{file}")
def get_thumbnail(width: int, collection: str, poi_id: str, file: str, data_dir: DataDir, cache_dir: CacheDir, policy: Policy) -> FileResponse:
    if collection == "photos-placeholder" and policy.public_mode:
        raise HTTPException(status_code=404)
    path = thumbnail(data_dir, cache_dir, collection, poi_id, file, width)
    if path is None:
        raise HTTPException(status_code=404)
    # 同一地址的缩略图不常变（原图换了才变），浏览器缓存一天
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
