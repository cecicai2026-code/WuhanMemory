"""照片缩略图的测试（板块 1B，2026-11-15 Cecilia 选了"后端生成缩略图"）。

立体场景原来下载原尺寸的照片（每张 80KB 到 1MB），胶卷幕一幕就超过 3MB。
现在后端按需生成限定宽度的 JPEG 缩略图，存在 data/thumbs/（不进 git），以后直接给缓存。
地址：GET /media/thumbs/{宽度}/{photos 或 photos-placeholder}/{景点 id}/{文件名}
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.media import get_thumb_cache_dir
from app.api.pois import get_data_dir
from app.core.site_policy import SitePolicy, get_site_policy
from app.main import app
from app.schemas.poi import Photo
from app.services.poi_view import PoiPresenter


def make_image(path: Path, size: tuple[int, int], fmt: str = "JPEG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (180, 90, 40)).save(path, fmt)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    make_image(d / "photos" / "spot-a" / "big.jpg", (2000, 1500))
    make_image(d / "photos" / "spot-a" / "small.jpg", (300, 200))
    make_image(d / "photos" / "spot-a" / "tall.png", (900, 1600), "PNG")
    make_image(d / "photos-placeholder" / "spot-a" / "p1.jpg", (1600, 1200))
    (d / "photos" / "spot-a" / "broken.jpg").write_bytes(b"not an image")
    return d


@pytest.fixture
def client(data_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_data_dir] = lambda: data_dir
    app.dependency_overrides[get_thumb_cache_dir] = lambda: tmp_path / "thumbs"
    yield TestClient(app)
    app.dependency_overrides.pop(get_data_dir, None)
    app.dependency_overrides.pop(get_thumb_cache_dir, None)


def image_of(content: bytes, tmp_path: Path) -> Image.Image:
    p = tmp_path / "got.jpg"
    p.write_bytes(content)
    return Image.open(p)


def test_big_photo_is_shrunk_to_the_width_as_jpeg(client: TestClient, tmp_path: Path) -> None:
    res = client.get("/media/thumbs/800/photos/spot-a/big.jpg")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    im = image_of(res.content, tmp_path)
    assert im.format == "JPEG"
    assert im.size == (800, 600)  # 按比例缩
    assert "max-age" in res.headers.get("cache-control", "")


def test_png_and_portrait_photos_work(client: TestClient, tmp_path: Path) -> None:
    res = client.get("/media/thumbs/480/photos/spot-a/tall.png")
    assert res.status_code == 200
    assert image_of(res.content, tmp_path).size == (480, 853)


def test_small_photo_is_not_enlarged(client: TestClient, tmp_path: Path) -> None:
    res = client.get("/media/thumbs/800/photos/spot-a/small.jpg")
    assert res.status_code == 200
    assert image_of(res.content, tmp_path).size == (300, 200)


def test_thumbnail_is_cached_and_redone_when_the_photo_changes(client: TestClient, data_dir: Path, tmp_path: Path) -> None:
    assert client.get("/media/thumbs/800/photos/spot-a/big.jpg").status_code == 200
    cached = tmp_path / "thumbs" / "800" / "photos" / "spot-a" / "big.jpg"
    assert cached.is_file()
    first = cached.stat().st_mtime_ns

    # 再要一次：直接用缓存，不重新生成
    assert client.get("/media/thumbs/800/photos/spot-a/big.jpg").status_code == 200
    assert cached.stat().st_mtime_ns == first

    # 原图换了（比缓存新）：重新生成
    src = data_dir / "photos" / "spot-a" / "big.jpg"
    make_image(src, (1000, 1000))
    os.utime(src, ns=(first + 10_000_000_000, first + 10_000_000_000))
    res = client.get("/media/thumbs/800/photos/spot-a/big.jpg")
    assert image_of(res.content, tmp_path).size == (800, 800)


@pytest.mark.parametrize(
    "path",
    [
        "/media/thumbs/1234/photos/spot-a/big.jpg",  # 宽度只能是规定的几种
        "/media/thumbs/800/elsewhere/spot-a/big.jpg",  # 只有两个目录
        "/media/thumbs/800/photos/spot-a/missing.jpg",
        "/media/thumbs/800/photos/spot-b/big.jpg",
        "/media/thumbs/800/photos/spot-a/broken.jpg",  # 不是图片
        "/media/thumbs/800/photos/..%2Fphotos-placeholder/spot-a/p1.jpg",
        "/media/thumbs/800/photos/spot-a/..%2F..%2Fphotos-placeholder%2Fspot-a%2Fp1.jpg",
        "/media/thumbs/800/photos/.hidden/big.jpg",
    ],
)
def test_bad_requests_are_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_placeholder_thumbnails_follow_public_mode(client: TestClient) -> None:
    assert client.get("/media/thumbs/800/photos-placeholder/spot-a/p1.jpg").status_code == 200
    app.dependency_overrides[get_site_policy] = lambda: SitePolicy(public_mode=True, owner_passcode="x" * 12)
    # 公开模式：占位照片不对外，缩略图也一样；自己拍的照常给
    assert client.get("/media/thumbs/800/photos-placeholder/spot-a/p1.jpg").status_code == 404
    assert client.get("/media/thumbs/800/photos/spot-a/big.jpg").status_code == 200


def test_photo_out_has_a_thumbnail_url(data_dir: Path) -> None:
    presenter = PoiPresenter(data_dir, date_today())
    own = presenter.photo("spot-a", Photo(file="big.jpg", caption="大图", license="own", author="Cecilia", takenAt=None))
    assert own.thumbUrl == "/media/thumbs/800/photos/spot-a/big.jpg"
    ph = presenter.photo(
        "spot-a",
        Photo(file="p1.jpg", caption="占位", license="third-party-placeholder", author="x", sourceUrl="https://example.com/a", retrievedAt=date_today()),
    )
    assert ph.thumbUrl == "/media/thumbs/800/photos-placeholder/spot-a/p1.jpg"
    gone = presenter.photo(
        "spot-a",
        Photo(file="nope.jpg", caption="不在本机", license="third-party-placeholder", author="x", sourceUrl="https://example.com/b", retrievedAt=date_today()),
    )
    assert gone.url is None and gone.thumbUrl is None


def date_today():  # type: ignore[no-untyped-def]
    from datetime import date

    return date(2026, 11, 15)
