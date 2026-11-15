"""路线接口：两个景点之间步行、公交地铁、驾车怎么走。

前端不直接调用高德 Web 服务，key 只在后端。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.pois import get_poi_repository
from app.core.config import settings
from app.repositories.poi_repository import PoiRepository
from app.repositories.route_cache_repository import RouteCacheRepository, SqliteRouteCacheRepository
from app.schemas.route import RouteCompareOut, RouteMode, RouteOut
from app.services.routing.amap import AmapRouteProvider
from app.services.routing.service import RouteProvider, RouteService, UnknownPoiError

router = APIRouter(prefix="/api/routes", tags=["routes"])


async def get_route_provider() -> AsyncIterator[RouteProvider]:
    async with httpx.AsyncClient() as client:
        yield AmapRouteProvider(settings.amap_web_service_key, settings.amap_base_url, client)


def get_route_cache() -> RouteCacheRepository:
    return SqliteRouteCacheRepository(settings.database_path)


def get_route_service(
    pois: Annotated[PoiRepository, Depends(get_poi_repository)],
    provider: Annotated[RouteProvider, Depends(get_route_provider)],
    cache: Annotated[RouteCacheRepository, Depends(get_route_cache)],
) -> RouteService:
    return RouteService(pois, provider, cache)


Service = Annotated[RouteService, Depends(get_route_service)]
FromId = Annotated[str, Query(alias="from", description="起点景点 id")]
ToId = Annotated[str, Query(alias="to", description="终点景点 id")]


def _places(service: RouteService, from_id: str, to_id: str):
    if from_id == to_id:
        raise HTTPException(status_code=400, detail="起点和终点是同一个景点")
    try:
        return service.places(from_id, to_id)
    except UnknownPoiError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/compare", response_model=RouteCompareOut)
async def compare_routes(service: Service, from_id: FromId, to_id: ToId) -> RouteCompareOut:
    """三种交通方式一起查。某一种没查成时，那一项 status 是 error，其他照常返回。"""
    _places(service, from_id, to_id)
    return await service.compare(from_id, to_id)


@router.get("", response_model=RouteOut)
async def get_route(service: Service, from_id: FromId, to_id: ToId, mode: Annotated[RouteMode, Query()]) -> RouteOut:
    origin, destination = _places(service, from_id, to_id)
    return await service.route(origin, destination, mode)
