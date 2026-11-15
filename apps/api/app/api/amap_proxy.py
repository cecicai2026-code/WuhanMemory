"""高德 JS API 安全密钥代理。

高德 JS API 2.0 的安全密钥有两种用法：明文写进网页，或者经过自己的代理服务器加上。
高德官方强烈建议后一种（https://lbs.amap.com/api/javascript-api-v2/guide/abc/jscode）。
这里就是那个代理，照着官方 nginx 示例写：

- 浏览器里设置 window._AMapSecurityConfig = { serviceHost: "<后端>/_AMapService" }，
  地图要发给高德的请求就会先发到这里。
- /_AMapService/v4/map/styles 转到 https://webapi.amap.com/v4/map/styles（自定义地图样式）；
  其余 /_AMapService/... 转到 https://restapi.amap.com/...。
- 转发时在查询参数末尾加上 jscode=<安全密钥>。安全密钥只在 apps/api/.env 里，浏览器拿不到。

只接受从本站页面发来的请求（看 Referer 或 Origin 是不是 CORS 白名单里的网址），
避免别的网站借用这个代理。这只能挡住普通网页，挡不住有意伪造请求头的程序。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings

router = APIRouter(tags=["amap-proxy"])

PREFIX = "/_AMapService"
STYLES_PATH = "v4/map/styles"
TIMEOUT_SECONDS = 10.0
# 原样转回浏览器的响应头。其余（长度、压缩、连接）由这边重新生成
PASS_HEADERS = ("content-type", "cache-control")


async def get_proxy_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        yield client


Client = Annotated[httpx.AsyncClient, Depends(get_proxy_client)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _origin(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def from_allowed_page(request: Request, allowed: list[str]) -> bool:
    origin = _origin(request.headers.get("origin")) or _origin(request.headers.get("referer"))
    return origin is not None and origin in {a.rstrip("/") for a in allowed}


def upstream_url(path: str, settings: Settings) -> str:
    if path == STYLES_PATH or path.startswith(STYLES_PATH + "/"):
        return f"{settings.amap_webapi_url.rstrip('/')}/{path}"
    return f"{settings.amap_base_url.rstrip('/')}/{path}"


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


@router.api_route(PREFIX + "/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def amap_proxy(path: str, request: Request, client: Client, settings: AppSettings) -> Response:
    if not settings.amap_security_js_code:
        return _error(503, "amap-security-missing", "后端没有配置高德安全密钥（apps/api/.env 里的 AMAP_SECURITY_JS_CODE）")
    if not from_allowed_page(request, settings.cors_origins):
        return _error(403, "amap-proxy-forbidden", "这个代理只给本站的地图页面用")

    # 照官方示例：原来的查询参数原样保留，末尾加上 jscode
    params = list(request.query_params.multi_items())
    params = [(k, v) for k, v in params if k != "jscode"]
    params.append(("jscode", settings.amap_security_js_code))

    try:
        upstream = await client.request(
            request.method,
            upstream_url(path, settings),
            params=params,
            content=await request.body() if request.method == "POST" else None,
            headers={"content-type": request.headers["content-type"]} if "content-type" in request.headers else None,
        )
    except httpx.HTTPError as exc:
        return _error(502, "amap-unreachable", f"连不上高德服务器：{type(exc).__name__}")

    headers = {k: v for k, v in upstream.headers.items() if k.lower() in PASS_HEADERS}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)
