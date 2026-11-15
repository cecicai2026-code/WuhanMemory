"""分享接口（板块 7）。

- POST   /api/itinerary-versions/{id}/share：给一个版本生成分享链接。已经有没撤回的链接时给回那一个（200），新建的是 201。
         没通过校验的版本不能分享（409）：没通过的行程不展示给用户，也就不给别人看。
- GET    /api/share/{slug}：分享页的内容，就是分享时绑定的那个版本。撤回了是 410，没有这个链接是 404。
- DELETE /api/share/{slug}：撤回。撤回后链接永远是撤回状态，再分享换新链接。

字段说明见 docs/architecture/api-contracts.md 的"分享"一节。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.planning import Itineraries
from app.core.config import settings
from app.repositories.share_link_repository import ShareLinkRepository, SqliteShareLinkRepository
from app.schemas.share import ShareLink, ShareLinkOut, SharePageOut

router = APIRouter(prefix="/api", tags=["share"])


def get_share_links() -> ShareLinkRepository:
    return SqliteShareLinkRepository(settings.database_path)


ShareLinks = Annotated[ShareLinkRepository, Depends(get_share_links)]


def link_out(link: ShareLink) -> ShareLinkOut:
    return ShareLinkOut(**link.model_dump(), path=f"/s/{link.slug}")


@router.post("/itinerary-versions/{version_id}/share", response_model=ShareLinkOut)
async def publish_share(version_id: str, response: Response, itineraries: Itineraries, links: ShareLinks) -> ShareLinkOut:
    version = itineraries.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"没有这份行程：{version_id}")
    if version.validation.status == "failed":
        raise HTTPException(status_code=409, detail="这份行程没通过校验，不能分享")
    existing = links.active_for_version(version_id)
    if existing is not None:
        response.status_code = 200
        return link_out(existing)
    # 两个请求同时来时，create 会给回另一个请求刚建的链接，不会建出第二个
    response.status_code = 201
    return link_out(links.create(version_id))


@router.get("/share/{slug}", response_model=SharePageOut)
async def get_share(slug: str, itineraries: Itineraries, links: ShareLinks) -> SharePageOut:
    link = links.get(slug)
    if link is None:
        raise HTTPException(status_code=404, detail=f"没有这个分享链接：{slug}")
    if link.revokedAt is not None:
        raise HTTPException(status_code=410, detail="这个分享链接已经撤回")
    version = itineraries.get_version(link.versionId)
    if version is None:  # 版本被删了（现在没有删除版本的功能，防万一）
        raise HTTPException(status_code=404, detail=f"这个分享链接指向的行程不在了：{slug}")
    return SharePageOut(slug=link.slug, createdAt=link.createdAt, version=version)


@router.delete("/share/{slug}", response_model=ShareLinkOut)
async def revoke_share(slug: str, links: ShareLinks) -> ShareLinkOut:
    link = links.revoke(slug)
    if link is None:
        raise HTTPException(status_code=404, detail=f"没有这个分享链接：{slug}")
    return link_out(link)
