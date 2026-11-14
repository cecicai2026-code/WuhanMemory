"""景点接口。只通过 PoiRepository 取数据。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.data_quality.rules import today_in_city
from app.repositories.poi_repository import PoiRepository, SqlitePoiRepository
from app.schemas.poi_api import PoiDetailResponse, PoiListOut
from app.services.poi_view import PoiPresenter

router = APIRouter(prefix="/api/pois", tags=["pois"])


def get_poi_repository() -> PoiRepository:
    return SqlitePoiRepository(settings.database_path)


def get_today() -> date:
    return today_in_city()


def get_data_dir() -> Path:
    return settings.data_dir


Repo = Annotated[PoiRepository, Depends(get_poi_repository)]
Today = Annotated[date, Depends(get_today)]
DataDir = Annotated[Path, Depends(get_data_dir)]


@router.get("", response_model=PoiListOut)
def list_pois(
    repo: Repo,
    today: Today,
    data_dir: DataDir,
    district: Annotated[str | None, Query(description="按所在区筛选，例如 武昌区")] = None,
    category: Annotated[str | None, Query(description="按类别筛选")] = None,
) -> PoiListOut:
    presenter = PoiPresenter(data_dir, today)
    pois = repo.list_pois(district=district, category=category)
    return PoiListOut(asOf=today, pois=[presenter.summary(p) for p in pois])


@router.get("/{poi_id}", response_model=PoiDetailResponse)
def get_poi(poi_id: str, repo: Repo, today: Today, data_dir: DataDir) -> PoiDetailResponse:
    poi = repo.get_poi(poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail=f"没有这个景点：{poi_id}")
    return PoiDetailResponse(asOf=today, poi=PoiPresenter(data_dir, today).detail(poi))
