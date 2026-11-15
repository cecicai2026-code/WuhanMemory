"""照片缩略图（板块 1B，2026-11-15）。

立体场景和列表里的照片都显示得不大，原图却有的上千像素宽、1MB 左右。这里按需把照片缩成
限定宽度的 JPEG，存在缓存目录里（默认 data/thumbs/，不进 git），以后直接给缓存；原图比缓存新时重新生成。
只缩小不放大。宽度只能是 ALLOWED_WIDTHS 里的几种，免得别人随便传宽度把缓存撑满。
"""

from __future__ import annotations

import re
from pathlib import Path

ALLOWED_WIDTHS = (480, 800)
# 照片在 data/ 下的两个目录：自己拍的、占位的
COLLECTIONS = ("photos", "photos-placeholder")
# 景点 id 和文件名只认这些字符，不能有 /、..、开头的点
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def thumb_url(collection: str, poi_id: str, file: str, width: int = 800) -> str:
    return f"/media/thumbs/{width}/{collection}/{poi_id}/{file}"


def thumbnail(data_dir: Path, cache_dir: Path, collection: str, poi_id: str, file: str, width: int) -> Path | None:
    """返回缩略图文件；参数不对、原图不存在或不是图片时返回 None。"""
    if width not in ALLOWED_WIDTHS or collection not in COLLECTIONS:
        return None
    if not _SAFE.match(poi_id) or not _SAFE.match(file) or ".." in file:
        return None
    base = (data_dir / collection).resolve()
    src = (base / poi_id / file).resolve()
    if base not in src.parents or not src.is_file():
        return None

    dst = cache_dir / str(width) / collection / poi_id / f"{Path(file).stem}.jpg"
    if dst.is_file() and dst.stat().st_mtime_ns >= src.stat().st_mtime_ns:
        return dst

    # 用到时才引用 Pillow：没装的话缩略图返回 404，网页退回用原图，后端其余功能照常
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        return None
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)  # 手机照片按拍摄方向转正
            im = im.convert("RGB")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".tmp")
            im.save(tmp, "JPEG", quality=80, optimize=True, progressive=True)
            tmp.replace(dst)  # 先写临时文件再换名，两个请求同时生成也不会读到写了一半的文件
    except (UnidentifiedImageError, OSError):
        return None
    return dst
