"""plan_single 和调用记录收集的测试（板块 6）：给定偏好、一种侧重、指定模型排一份。

用两个假模型（名字叫 qwen、doubao，只是假 provider）和假高德，不调用真实接口；景点是虚构的测试景点。
测试景点的开放时间：周二到周日 09:00–17:00，最晚 16:00 入场，周一闭馆；建议游玩 120 分钟。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.data_quality.rules import CITY_TZ
from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.planning_round_repository import SqlitePlanningRoundRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.planning import TravelerPreferences
from app.services.llm.collect import collect_calls
from app.services.llm.errors import LLMAuthError
from app.services.llm.gateway import LLMGateway
from app.services.planning.pipeline import PlanningPipeline
from app.services.routing.service import RouteService
from tests.llm_fakes import FakeProvider, Sleeps
from tests.test_planning_pipeline import TODAY, FakeRouteProvider, MemoryPois, plan, poi

POIS = [poi("a", tags=["历史", "5A"]), poi("b", tags=["老街"]), poi("c", tags=["湖景"])]
WALKS = {("a", "b", "walk"): 12, ("b", "a", "walk"): 12, ("b", "c", "walk"): 10}
PREFS = TravelerPreferences(days=1, startDate="2026-11-17")  # 周二

GOOD = plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")])


class TwoModels:
    def __init__(self, tmp_path: Path, qwen: list[Any], doubao: list[Any]):
        self.qwen = FakeProvider("qwen", script=qwen)
        self.doubao = FakeProvider("doubao", script=doubao)
        self.gateway = LLMGateway(providers={"qwen": self.qwen, "doubao": self.doubao}, default_provider="qwen", sleep=Sleeps())
        db = tmp_path / "t.db"
        pois = MemoryPois(POIS)
        self.itineraries = SqliteItineraryRepository(db)
        routes = RouteService(pois, FakeRouteProvider(WALKS), SqliteRouteCacheRepository(db),
                              now=lambda: datetime(2026, 11, 15, 12, 0, tzinfo=CITY_TZ))
        self.pipeline = PlanningPipeline(gateway=self.gateway, pois=pois, routes=routes, itineraries=self.itineraries,
                                         conversations=SqliteConversationRepository(db),
                                         rounds=SqlitePlanningRoundRepository(db), today=lambda: TODAY)

    async def run(self, provider: str, emphasis: str = "classic", prefs: TravelerPreferences = PREFS,
                  transit: list[str] | None = None):
        with collect_calls() as calls:
            out = await self.pipeline.plan_single(message="测试请求", prefs=prefs, emphasis=emphasis, provider=provider,
                                                  transit=transit)
        return out, calls


async def test_passes_first_time_and_saves_first_report(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD], [])
    out, calls = await s.run("qwen")
    assert out.error is None and out.version is not None
    v = out.version
    assert v.planner.provider == "qwen" and v.planner.rounds == 1 and v.emphasis == "classic"
    # 第一版就是最终版：第一版报告也存下来，草稿不重复存
    assert v.firstValidation is not None and v.firstValidation.status == v.validation.status
    assert v.firstDraft is None
    assert s.itineraries.get_version(v.id) is not None
    # 不抽偏好：只调用了一次排行程
    assert [c.task for c in calls] == ["generate_itinerary"]
    assert len(s.doubao.calls) == 0


async def test_repaired_keeps_first_draft_and_errors(tmp_path: Path) -> None:
    late = plan([("a", "09:30", "11:30"), ("b", "12:00", "17:30")])  # b 停留 330 分钟，程序推下来 17:00 关门后才离开
    s = TwoModels(tmp_path, [late, GOOD], [])
    out, calls = await s.run("qwen")
    v = out.version
    assert v is not None and v.planner.rounds == 2
    assert v.firstValidation is not None and "after-close" in [i.code for i in v.firstValidation.errors]
    # 程序推的钟点：11:30 离开 a，走 12 分钟 + 10 分钟，取整到 11:55
    assert v.firstDraft is not None and (v.firstDraft.days[0].stops[1].arrive, v.firstDraft.days[0].stops[1].leave) == ("11:55", "17:25")
    # 模型给的原样存着
    assert v.firstOutline is not None and v.firstOutline.days[0].stops[1].stayMinutes == 330
    assert v.outline is not None and v.outline.days[0].stops[1].stayMinutes == 120
    assert v.validation.errors == []
    assert [c.task for c in calls] == ["generate_itinerary", "repair_itinerary"]


async def test_model_error_is_returned_not_raised(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [LLMAuthError("测试：出错")], [])
    out, calls = await s.run("qwen")
    assert out.version is None and out.error is not None and "测试：出错" in out.error
    # 失败的调用也收集到了
    assert len(calls) == 1 and not calls[0].ok


async def test_repair_error_keeps_first_round(tmp_path: Path) -> None:
    late = plan([("a", "09:30", "11:30"), ("b", "12:00", "17:30")])
    s = TwoModels(tmp_path, [late, LLMAuthError("测试：修正出错")], [])
    out, _ = await s.run("qwen")
    assert out.version is not None and out.version.validation.status == "failed"
    assert out.repair_error is not None and "修正出错" in out.repair_error


async def test_two_models_in_parallel_get_same_prompt_and_own_calls(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD], [plan([("a", "10:00", "12:00"), ("b", "12:30", "14:30")])])
    # 真实交通表先算一份、两边共用（ModelComparer 就是这样做的）：同时跑时，各算各的会读到对方刚查进缓存的路线
    transit = s.pipeline.transit_for(PREFS, "classic")
    (q, q_calls), (d, d_calls) = await asyncio.gather(s.run("qwen", transit=transit), s.run("doubao", transit=transit))
    # 两边收到的提示词一模一样：同样的偏好、候选、侧重、交通表
    assert s.qwen.calls[0] == s.doubao.calls[0]
    assert "【两站之间的真实交通】" in s.qwen.calls[0][-1].content
    # 每边只收集到自己的调用
    assert [c.provider for c in q_calls] == ["qwen"] and [c.provider for c in d_calls] == ["doubao"]
    assert q.version.planner.provider == "qwen" and d.version.planner.provider == "doubao"  # type: ignore[union-attr]


async def test_transit_table_reaches_the_prompt(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD, GOOD], [])
    await s.run("qwen")  # 第一次排完，a 和 b 之间的步行进了缓存
    await s.run("qwen")
    first, second = s.qwen.calls[0][-1].content, s.qwen.calls[1][-1].content
    assert "a—b 没查到真实时间，直线" in first
    assert "a↔b 步行 12 分钟" in second or "a→b 步行 12 分钟" in second


async def test_emphasis_rules_apply(tmp_path: Path) -> None:
    # 轻松少走路：每天最多 3 站，这里排了 3 站以内但 17:30 后才结束 → 错误，修正一次
    late = plan([("a", "14:00", "16:00"), ("b", "16:30", "18:00")])
    s = TwoModels(tmp_path, [late, plan([("a", "09:30", "11:30")])], [])
    out, _ = await s.run("qwen", emphasis="relaxed")
    v = out.version
    assert v is not None and v.emphasis == "relaxed" and v.planner.rounds == 2
    assert "emphasis-ends-late" in [i.code for i in v.firstValidation.errors]  # type: ignore[union-attr]


async def test_needs_days(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [], [])
    with pytest.raises(ValueError):
        await s.run("qwen", prefs=TravelerPreferences())


async def test_no_date_means_undecided(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD], [])
    out, _ = await s.run("qwen", prefs=TravelerPreferences(days=1))
    assert out.version is not None and out.version.preferences.dateUndecided
    assert "date-unknown" in [i.code for i in out.version.validation.issues]


async def test_relaxed_plan_says_it_uses_relaxed_pace(tmp_path: Path) -> None:
    # 和 /map 的三份方案同一条规则（main 上 d08e962）：侧重改了节奏，就不写共用的"节奏：适中（按默认）"
    s = TwoModels(tmp_path, [plan([("a", "09:30", "11:30")])], [])
    out, _ = await s.run("qwen", emphasis="relaxed")
    assert out.version is not None
    pace = [d for d in out.version.defaultsUsed if d.startswith("节奏：")]
    assert pace == ["节奏：轻松（这份是「轻松少走路」，按轻松排）"]
    assert out.defaults == out.version.defaultsUsed
