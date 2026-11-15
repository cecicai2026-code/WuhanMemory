"""中英双语：后端按请求的语言写给人看的话（app/core/lang.py）。

规划和对比的逻辑不随语言变（标签、兴趣、侧重规则都按中文资料判断），只换说法；
英文版行程里存的是景点资料的英文译文，门票计算要认得英文票名。
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.core.lang import L, current_lang, use_lang
from app.main import app
from app.schemas.planning import TravelerPreferences
from app.services.planning.emphasis import EMPHASES
from app.services.planning.metrics import plan_metrics
from app.services.planning.pipeline import stage_label
from app.services.planning.preferences import question_for
from tests.test_plan_metrics import stop, version

NIGHT_EN = {
    "free": False,
    "items": [
        {"name": "Day ticket, full price", "priceCny": 70},
        {"name": "Day ticket, half price", "priceCny": 35},
        {"name": "Night ticket, adult (Fri–Sun and public holidays)", "priceCny": 150},
        {"name": "Night ticket, adult (Mon–Thu)", "priceCny": 120},
    ],
}


def test_default_is_chinese() -> None:
    assert current_lang() == "zh"
    assert L("中文", "English") == "中文"


def test_use_lang_switches_and_restores() -> None:
    with use_lang("en"):
        assert L("中文", "English") == "English"
        assert EMPHASES["classic"].label == "The classics"
        assert stage_label("routing") == "Looking up real travel times"
    assert EMPHASES["classic"].label == "经典必去"


def test_question_in_english() -> None:
    prefs = TravelerPreferences()
    with use_lang("en"):
        q = question_for(prefs, set(), date(2026, 11, 15))
    assert q is not None
    assert "How many days" in q.text
    assert not any("一" <= ch <= "鿿" for ch in q.text)


def test_english_ticket_names_are_understood() -> None:
    with use_lang("en"):
        day = plan_metrics(version(([stop("a", "09:00", "11:00", ticket=NIGHT_EN)], []))).tickets[0]
        tue = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=NIGHT_EN)], []), start="2026-11-17")).tickets[0]
        fri = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=NIGHT_EN)], []), start="2026-11-20")).tickets[0]
        undated = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=NIGHT_EN)], []), start=None)).tickets[0]
    # 半价票不算成人全票；夜场按星期几分价钱
    assert (day.minCny, day.maxCny) == (70, 70)
    assert day.label == "Day ticket, full price ¥70"
    assert (tue.minCny, fri.minCny) == (120, 150)
    assert (undated.minCny, undated.maxCny) == (120, 150)
    assert undated.label == "Adult night ticket ¥120 or ¥150 (date not set)"


def test_api_error_detail_follows_request_language() -> None:
    client = TestClient(app)
    zh = client.get("/api/itinerary-versions/nope").json()["detail"]
    en = client.get("/api/itinerary-versions/nope", headers={"X-Lang": "en"}).json()["detail"]
    assert zh == "没有这份行程：nope"
    assert en == "No such trip: nope"
