"""中英双语：每个请求用哪种语言（2026-11-15 Cecilia 定，网站上有"中 / EN"切换）。

前端把语言放在三处之一，按这个顺序认：
1. 查询参数 ?lang=en（网站在服务器端取数据时用，例如 GET /api/pois?lang=en）
2. 请求头 X-Lang: en（浏览器里调接口时用，见 apps/web/lib/planning-client.ts）
3. cookie wm-lang=en（浏览器经网站转发过来的请求自带）
都没有时用中文。

后端写给人看的话（校验说明、提示、对比表）按这个语言写；规划时让模型用这种语言写理由和反问。
景点资料的英文是译文，放在 data/pois/en/，见 app/services/poi_i18n.py。
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, Request

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


def get_lang(request: Request) -> LangCode:
    return (
        parse_lang(request.query_params.get("lang"))
        or parse_lang(request.headers.get(LANG_HEADER))
        or parse_lang(request.cookies.get(LANG_COOKIE))
        or "zh"
    )


Lang = Annotated[LangCode, Depends(get_lang)]


def tr(lang: LangCode, zh: str, en: str) -> str:
    """按语言取一句话：tr(lang, "中文", "English")。中英两句写在一起，改的时候两边都看得见。"""
    return en if lang == "en" else zh
