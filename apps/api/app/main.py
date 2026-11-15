import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.amap_proxy import router as amap_proxy_router
from app.api.comparisons import router as comparisons_router
from app.api.llm import router as llm_router
from app.api.planning import router as planning_router
from app.api.pois import router as pois_router
from app.api.routing import router as routing_router
from app.api.routes import router
from app.core.config import settings
from app.data_quality.rules import today_in_city
from app.db.import_pois import import_pois
from app.db.sqlite import connect

logger = logging.getLogger("wuhanmemory")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # 启动时把 data/pois/*.json 导入 SQLite（ADR 0003）
    conn = connect(settings.database_path)
    try:
        report, imported = import_pois(conn, settings.data_dir, today_in_city())
    finally:
        conn.close()
    logger.warning(
        "景点导入：%d 个导入，错误 %d 个，警告 %d 个",
        len(imported),
        len(report.errors),
        len(report.warnings),
    )
    for issue in report.errors:
        logger.warning("%s", issue)
    yield


app = FastAPI(title="WuhanMemory API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(planning_router)
app.include_router(pois_router)
app.include_router(amap_proxy_router)
app.include_router(routing_router)
app.include_router(llm_router)
app.include_router(comparisons_router)

# 景点照片。自己拍的在 data/photos/，官网占位的在 data/photos-placeholder/（不进 git）
app.mount("/media/photos", StaticFiles(directory=settings.data_dir / "photos", check_dir=False), name="photos")
app.mount(
    "/media/photos-placeholder",
    StaticFiles(directory=settings.data_dir / "photos-placeholder", check_dir=False),
    name="photos-placeholder",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
    }
