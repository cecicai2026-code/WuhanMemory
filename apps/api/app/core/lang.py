"""中英双语：每个请求用哪种语言（2026-11-15 Cecilia 定，网站上有"中 / EN"切换）。

前端把语言放在三处之一，按这个顺序认：
1. 查询参数 ?lang=en（网站在服务器端取数据时用，例如 GET /api/pois?lang=en）
2. 请求头 X-Lang: en（浏览器里调接口时用，见 apps/web/lib/planning-client.ts）
3. cookie wm-lang=en（浏览器经网站转发过来的请求自带）
都没有时用中文。

后端写给人看的话（校验说明、提示、对比表）按这个语言写；规划时让模型用这种语言写理由和反问。
景点资料的英文是译文，放在 data/pois/en/，见 app/services/poi_i18n.py。

规划、对比这些链路很长，语言不一层层传参数，而是放在 contextvar 里：
LangMiddleware 在每个请求开始时按上面的规则设好，后台任务开始时用 use_lang() 再设一次（任务记着发起时的语言）。
链路里任何地方写给人看的话都用 L("中文", "English")。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated, Literal

from fastapi import Depends, Request
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

LangCode = Literal["zh", "en"]
LANG_HEADER = "X-Lang"
LANG_COOKIE = "wm-lang"


def parse_lang(value: str | None) -> LangCode | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v.startswith("en"):
        return "en"
    if v.startswith("zh"):
        return "zh"
    return None


def lang_of(conn: HTTPConnection) -> LangCode:
    return (
        parse_lang(conn.query_params.get("lang"))
        or parse_lang(conn.headers.get(LANG_HEADER))
        or parse_lang(conn.cookies.get(LANG_COOKIE))
        or "zh"
    )


def get_lang(request: Request) -> LangCode:
    return lang_of(request)


Lang = Annotated[LangCode, Depends(get_lang)]


def tr(lang: LangCode, zh: str, en: str) -> str:
    """按语言取一句话：tr(lang, "中文", "English")。中英两句写在一起，改的时候两边都看得见。"""
    return en if lang == "en" else zh


_current: ContextVar[LangCode] = ContextVar("wm_lang", default="zh")


def current_lang() -> LangCode:
    return _current.get()


def L(zh: str, en: str) -> str:
    """按当前请求（或当前后台任务）的语言取一句话。"""
    return en if _current.get() == "en" else zh


@contextmanager
def use_lang(lang: LangCode) -> Iterator[None]:
    """在这段代码里用 lang（后台任务、测试用）。"""
    token = _current.set(lang)
    try:
        yield
    finally:
        _current.reset(token)


class LangMiddleware:
    """每个请求开始时按 ?lang、X-Lang、cookie 设好当前语言（纯 ASGI 中间件，contextvar 会传到接口和它的后台任务）。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        with use_lang(lang_of(HTTPConnection(scope))):
            await self.app(scope, receive, send)


async def run_in_lang(lang: LangCode, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    """后台任务用：按发起请求时的语言跑（规划、对比的任务写进对话和记录的话都用这种语言）。"""
    with use_lang(lang):
        return await fn(*args, **kwargs)
