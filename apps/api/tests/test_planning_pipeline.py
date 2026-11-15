"""规划链路的测试。不调用真实模型，也不联网：

- 模型是 tests/llm_fakes.py 的假 provider，按剧本依次回答"抽偏好""排行程""修正"；
- 高德是下面的 FakeRouteProvider，按表返回手写的分钟数；
- 景点是虚构的测试景点（tests/poi_factory.py），存在内存里；对话和行程存在临时 SQLite 文件里。

2026-11-17 是周二，2026-11-16 是周一。测试景点周一闭馆。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.data_quality.rules import CITY_TZ
from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.planning_round_repository import SqlitePlanningRoundRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.poi import PoiFile
from app.schemas.route import GeoPointOut, RouteCost
from app.services.llm.errors import LLMAuthError, LLMError
from app.services.llm.gateway import LLMGateway
from app.services.planning.pipeline import PlanningPipeline
from app.services.routing.amap import ProviderRoute, RouteProviderError
from app.services.routing.service import RouteService
from tests.llm_fakes import FakeProvider, Sleeps
from tests.poi_factory import clean_poi, hours

TODAY = date(2026, 11, 15)
COORDS = {"a": (114.30, 30.55), "b": (114.31, 30.56), "c": (114.25, 30.60), "food": (114.29, 30.54)}


class MemoryPois:
    def __init__(self, pois: list[dict[str, Any]]):
        self._pois = [PoiFile.model_validate(p) for p in pois]

    def list_pois(self, *, district: str | None = None, category: str | None = None) -> list[PoiFile]:
        return list(self._pois)

    def get_poi(self, poi_id: str) -> PoiFile | None:
        return next((p for p in self._pois if p.id == poi_id), None)


class FakeRouteProvider:
    """table[(起点 id, 终点 id, 方式)] = 分钟数；"none" 表示高德没给方案；"error" 表示查询出错。没写的按 99 分钟。"""

    name = "fake"

    def __init__(self, table: dict[tuple[str, str, str], Any]):
        self.table = table
        self.calls: list[tuple[str, str, str]] = []
        self._ids = {v: k for k, v in COORDS.items()}

    async def plan(self, mode: str, origin: GeoPointOut, destination: GeoPointOut, depart_at: datetime) -> ProviderRoute:
        key = (self._ids[(origin.lng, origin.lat)], self._ids[(destination.lng, destination.lat)], mode)
        self.calls.append(key)
        value = self.table.get(key, 99)
        if value == "error":
            raise RouteProviderError("amap-test", "测试：查询出错")
        if value == "none":
            return ProviderRoute(status="none", api="/test", raw={}, reason="测试：没有方案")
        return ProviderRoute(
            status="ok",
            api="/test",
            raw={},
            durationMinutes=value,
            distanceMeters=value * 80,
            cost=RouteCost(kind="free", amountCny=0, note="测试"),
            polyline=[origin, destination],
        )


def poi(poi_id: str, **changes: Any) -> dict[str, Any]:
    p = clean_poi(poi_id, **changes)
    lng, lat = COORDS[poi_id]
    p["location"]["value"].update({"lng": lng, "lat": lat})
    return p


def prefs(**fields: Any) -> str:
    base = {"days": None, "startDate": None, "dateUndecided": False, "pace": None, "interests": [], "budget": None,
            "party": None, "transport": None, "mustVisit": [], "avoid": [], "notes": None}
    base.update(fields)
    return json.dumps(base, ensure_ascii=False)


def plan(*days: list[tuple[str, str, str]], title: str = "测试行程") -> str:
    return json.dumps(
        {
            "title": title,
            "days": [
                {"dayNumber": i, "theme": f"第{i}天主题", "stops": [{"poiId": p, "arrive": a, "leave": l, "reason": "测试"} for p, a, l in s]}
                for i, s in enumerate(days, start=1)
            ],
        },
        ensure_ascii=False,
    )


class Setup:
    def __init__(self, tmp_path: Path, script: list[Any], routes: dict[tuple[str, str, str], Any] | None = None,
                 pois: list[dict[str, Any]] | None = None, emphases: tuple[str, ...] = ("classic",)):
        # 板块 5 的测试只排一份（经典必去；测试景点没有 5A 标签，所以和板块 5 的单份规划一样）；三份的测试见 test_planning_rounds.py
        self.model = FakeProvider("fake", script=script)
        self.gateway = LLMGateway(providers={"fake": self.model}, default_provider="fake", sleep=Sleeps())
        self.routes = FakeRouteProvider(routes or {})
        self.poi_repo = MemoryPois(pois if pois is not None else [poi("a"), poi("b"), poi("c")])
        db = tmp_path / "t.db"
        self.conversations = SqliteConversationRepository(db)
        self.itineraries = SqliteItineraryRepository(db)
        self.rounds = SqlitePlanningRoundRepository(db)
        service = RouteService(self.poi_repo, self.routes, SqliteRouteCacheRepository(db),
                               now=lambda: datetime(2026, 11, 15, 12, 0, tzinfo=CITY_TZ))
        self.pipeline = PlanningPipeline(gateway=self.gateway, pois=self.poi_repo, routes=service,
                                         itineraries=self.itineraries, conversations=self.conversations,
                                         rounds=self.rounds, today=lambda: TODAY, emphases=emphases)
        self.conv = self.conversations.create()
        self.stages: list[str] = []

    async def send(self, text: str, provider: str | None = None):
        self.conversations.add_message(self.conv.id, "user", text)
        return await self.pipeline.handle(self.conv.id, text, provider=provider, on_stage=self.stages.append)

    def prompt(self, call: int) -> str:
        """第 call 次请求（从 0 数）发给模型的用户提示词。"""
        return self.model.calls[call][-1].content


DATED = dict(days=1, startDate="2026-11-17")


# ---------- 反问 ----------


async def test_asks_for_days_and_date_then_plans(tmp_path: Path) -> None:
    s = Setup(tmp_path, [
        prefs(interests=["历史文化"]),
        prefs(days=1, dateUndecided=True, interests=["历史文化"]),
        plan([("a", "09:30", "11:30")]),
    ])
    first = await s.send("想去武汉看看历史")
    assert first.kind == "question" and "几天" in first.reply and "哪天出发" in first.reply
    assert first.version is None and len(s.model.calls) == 1  # 反问时不生成行程

    second = await s.send("一天，日期没定")
    assert second.kind == "itinerary" and second.version is not None
    assert second.version.frame.startDate is None
    assert "date-unknown" in [i.code for i in second.version.validation.issues]
    assert any("日期" in d for d in second.version.defaultsUsed)
    # 第二次抽偏好时，把第一次知道的带给了模型
    assert "历史文化" in s.prompt(1)


async def test_date_is_asked_only_once(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(), prefs(days=1), plan([("a", "09:30", "11:30")])])
    assert (await s.send("去武汉")).kind == "question"
    # 用户只回答了天数，没说日期：不再追问，按日期未定排
    out = await s.send("一天")
    assert out.kind == "itinerary" and out.version is not None and out.version.preferences.dateUndecided


async def test_past_date_is_questioned(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(days=1, startDate="2026-10-01")])
    out = await s.send("10 月 1 日去一天")
    assert out.kind == "question" and "已经过去" in out.reply


# ---------- 一次通过 ----------


async def test_one_round_uses_real_transport_and_saves(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED, pace="moderate", transport="metro"),
                         plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")])],
              routes={("a", "b", "walk"): 12})
    out = await s.send("下周二去一天")
    v = out.version
    assert out.kind == "itinerary" and v is not None
    assert v.validation.status == "passed", v.validation.issues
    assert v.versionNumber == 1 and v.planner.rounds == 1 and v.planner.provider == "fake"
    assert v.planner.model == "fake-model-1"
    leg = v.days[0].legs[0]
    assert leg.route.mode == "walk" and leg.route.durationMinutes == 12 and "步行" in leg.choice
    assert v.days[0].date == date(2026, 11, 17)
    # 行程卡上的资料来自景点库，带核实状态
    assert v.days[0].stops[0].facts.payment.value is not None
    assert v.days[0].stops[0].name == "测试景点a"
    assert s.stages == ["understanding", "selecting", "generating", "routing", "validating", "saving"]
    assert [m.kind for m in s.conversations.messages(s.conv.id)] == [None, "itinerary"]
    assert s.itineraries.get_version(v.id) is not None
    assert [c.content for c in s.model.calls[1] if c.role == "system"][0].startswith("你是武汉旅行规划助手的\"排行程\"")


async def test_candidates_reach_the_model_with_ids(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED, interests=["美食"]), plan([("a", "09:30", "11:30")])])
    await s.send("吃")
    prompt = s.prompt(1)
    for poi_id in ("a", "b", "c"):
        assert f'"id": "{poi_id}"' in prompt
    assert "【两站之间的真实交通】" in prompt and "a—b 没查到真实时间，直线" in prompt  # 缓存还是空的


# ---------- 交通方式 ----------


async def test_long_walk_uses_preferred_mode(tmp_path: Path) -> None:
    routes = {("a", "c", "walk"): 50, ("a", "c", "transit"): 30, ("a", "c", "drive"): 20}
    s = Setup(tmp_path, [prefs(**DATED, transport="taxi"), plan([("a", "09:30", "11:30"), ("c", "12:30", "15:00")])],
              routes=routes)
    v = (await s.send("打车")).version
    assert v is not None and v.days[0].legs[0].route.mode == "drive"


async def test_no_transit_falls_back_to_walk(tmp_path: Path) -> None:
    routes = {("a", "c", "walk"): 25, ("a", "c", "transit"): "none"}
    s = Setup(tmp_path, [prefs(**DATED, transport="metro"), plan([("a", "09:30", "11:30"), ("c", "12:30", "15:00")])],
              routes=routes)
    leg = (await s.send("地铁")).version.days[0].legs[0]  # type: ignore[union-attr]
    assert leg.route.mode == "walk" and "改步行" in leg.choice


async def test_route_error_becomes_warning(tmp_path: Path) -> None:
    routes = {("a", "c", "walk"): "error", ("a", "c", "transit"): "error"}
    s = Setup(tmp_path, [prefs(**DATED), plan([("a", "09:30", "11:30"), ("c", "12:30", "15:00")])], routes=routes)
    v = (await s.send("去")).version
    assert v is not None and v.validation.status == "warning"
    assert [i.code for i in v.validation.issues] == ["route-unknown"]


async def test_routes_are_cached(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED), plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")]),
                         prefs(**DATED), plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")])],
              routes={("a", "b", "walk"): 10})
    await s.send("一")
    await s.send("再来")
    assert s.routes.calls == [("a", "b", "walk")]


# ---------- 修正 ----------


async def test_errors_go_back_to_model_once_and_get_fixed(tmp_path: Path) -> None:
    routes = {("a", "c", "walk"): 50, ("a", "c", "transit"): 40}
    s = Setup(tmp_path, [
        prefs(**DATED),
        plan([("a", "09:30", "11:30"), ("c", "11:40", "14:00")]),  # 只留 10 分钟
        plan([("a", "09:30", "11:30"), ("c", "12:30", "14:30")]),
    ], routes=routes)
    out = await s.send("去")
    v = out.version
    assert out.kind == "itinerary" and v is not None and v.validation.status == "passed"
    assert v.planner.rounds == 2 and v.planner.firstRoundStatus == "failed" and v.planner.firstRoundErrors == 1
    assert "repairing" in s.stages
    repair = s.prompt(2)
    assert "公交地铁要 40 分钟，行程只留了 10 分钟" in repair  # 具体错误
    assert "公交地铁 40 分钟" in repair  # 真实交通时间
    assert '"arrive":"11:40"' in repair  # 上一次的行程
    system = [m.content for m in s.model.calls[2] if m.role == "system"][0]
    assert "真实交通时间 + 10 分钟" in system
    assert "修正" in out.reply


async def test_still_failing_after_repair_is_not_shown_as_ok(tmp_path: Path) -> None:
    bad = plan([("a", "10:00", "12:00")])
    s = Setup(tmp_path, [prefs(days=1, startDate="2026-11-16"), bad, bad])  # 周一闭馆
    out = await s.send("周一去")
    assert out.kind == "failed"
    assert out.version is not None and out.version.validation.status == "failed"
    assert "不能展示" in out.reply and "没通过校验" in out.reply
    # 没通过的也存下来，标 failed（板块 6 要比较）
    assert s.itineraries.get_version(out.version.id).validation.status == "failed"  # type: ignore[union-attr]
    assert [m.kind for m in s.conversations.messages(s.conv.id)][-1] == "failed"
    assert len(s.model.calls) == 3  # 只修正一次


async def test_made_up_place_is_rejected(tmp_path: Path) -> None:
    s = Setup(tmp_path, [
        prefs(**DATED),
        plan([("a", "09:30", "11:30"), ("hogwarts", "13:00", "15:00")]),
        plan([("a", "09:30", "11:30"), ("hogwarts", "13:00", "15:00")]),
    ])
    out = await s.send("去")
    assert out.kind == "failed" and out.version is not None
    assert "unknown-poi" in [i.code for i in out.version.validation.errors]
    # 快照里只有真实存在的景点，模型原样的输出留在 draft 里
    assert [st.poiId for st in out.version.days[0].stops] == ["a"]
    assert [st.poiId for st in out.version.draft.days[0].stops] == ["a", "hogwarts"]


# ---------- 候选 ----------


async def test_avoided_place_is_not_a_candidate(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED, avoid=["测试景点b"]), plan([("b", "09:30", "11:30")]), plan([("a", "09:30", "11:30")])])
    out = await s.send("不去 b")
    assert '"id": "b"' not in s.prompt(1)
    # 模型还是排了 b：算"不在候选里"，修正后换成 a
    assert out.version is not None and out.version.planner.firstRoundStatus == "failed"
    assert out.version.validation.status == "passed"


async def test_must_visit_outside_library_is_told(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED, mustVisit=["测试景点c", "不存在的塔"]), plan([("c", "09:30", "11:30")])])
    v = (await s.send("要去 c 和塔")).version
    assert v is not None
    assert any("不存在的塔" in d and "不在景点库" in d for d in v.defaultsUsed)
    assert '"mustVisit": true' in s.prompt(1)


async def test_defaults_are_listed(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED), plan([("a", "09:30", "11:30")])])
    v = (await s.send("去")).version
    assert v is not None
    assert any("节奏：适中" in d for d in v.defaultsUsed) and any("交通：地铁公交优先" in d for d in v.defaultsUsed)


# ---------- 第二条消息 ----------


async def test_follow_up_message_makes_version_two(tmp_path: Path) -> None:
    s = Setup(tmp_path, [
        prefs(**DATED), plan([("a", "09:30", "11:30")]),
        prefs(**DATED, notes="下午再去一个"), plan([("a", "09:30", "11:30"), ("b", "13:00", "15:00")]),
    ], routes={("a", "b", "walk"): 10})
    v1 = (await s.send("去")).version
    v2 = (await s.send("下午再去一个")).version
    assert v1 is not None and v2 is not None
    assert v2.itineraryId == v1.itineraryId and v2.versionNumber == 2
    assert "【上一版行程】" in s.prompt(3)


# ---------- 模型 ----------


async def test_selected_provider_is_used_for_every_call(tmp_path: Path) -> None:
    other = FakeProvider("other", script=[prefs(**DATED), plan([("a", "09:30", "11:30")])], model="other-model")
    s = Setup(tmp_path, [])
    s.pipeline.gateway = LLMGateway(providers={"fake": s.model, "other": other}, default_provider="fake", sleep=Sleeps())
    v = (await s.send("去", provider="other")).version
    assert v is not None and v.planner.provider == "other" and v.planner.model == "other-model"
    assert s.model.calls == []
    assert s.conversations.messages(s.conv.id)[-1].provider == "other"


async def test_model_error_propagates(tmp_path: Path) -> None:
    s = Setup(tmp_path, [LLMAuthError("测试：key 无效")])
    with pytest.raises(LLMError):
        await s.send("去")
    assert s.itineraries.list_versions("nope") == []


async def test_unknown_opening_hours_never_passes(tmp_path: Path) -> None:
    s = Setup(tmp_path, [prefs(**DATED), plan([("a", "09:30", "11:30")])],
              pois=[poi("a", openingHours=hours(None))])
    v = (await s.send("去")).version
    assert v is not None and v.validation.status == "warning"
    assert any("开放时间未知，无法校验" in i.message for i in v.validation.issues)
    assert v.days[0].stops[0].facts.openingHours.status == "missing"


async def test_generation_timeout_is_not_retried(tmp_path: Path) -> None:
    from app.services.llm.errors import LLMTimeoutError

    s = Setup(tmp_path, [prefs(**DATED), LLMTimeoutError("测试：超时"), plan([("a", "09:30", "11:30")])])
    with pytest.raises(LLMTimeoutError):
        await s.send("去")
    assert len(s.model.calls) == 2  # 抽偏好一次、排行程一次，超时后没有再发
