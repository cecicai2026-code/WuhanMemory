"""一轮三份方案的测试（板块 5B）：并行生成、各自校验和修正、去掉几乎一样的、没通过的不展示、每份存成版本。

用假模型和假高德，不调用真实接口；景点是虚构的测试景点，标签用真实资料里的写法（规则按标签判断）。
测试景点的开放时间：周二到周日 09:00–17:00，最晚 16:00 入场，周一闭馆；建议游玩 120 分钟。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.llm.errors import LLMAuthError
from tests.test_planning_pipeline import Setup, plan, poi, prefs

DATED = dict(days=1, startDate="2026-11-17")  # 周二
ALL = ("classic", "relaxed", "culture")
POIS = [poi("a", tags=["历史", "5A"]), poi("b", tags=["老街"]), poi("c", tags=["湖景"])]
WALKS = {("a", "b", "walk"): 12, ("b", "a", "walk"): 12}

CLASSIC = plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")], title="经典")
RELAXED = plan([("c", "10:00", "12:30")], title="轻松")
CULTURE = plan([("a", "09:00", "11:00"), ("b", "13:00", "16:30")], title="文化")


def setup(tmp_path: Path, script: list[Any], routes: dict[tuple[str, str, str], Any] | None = None) -> Setup:
    return Setup(tmp_path, script, routes={**WALKS, **(routes or {})}, pois=POIS, emphases=ALL)


def by_emphasis(out: Any) -> dict[str, Any]:
    return {p.emphasis: p for p in out.round.plans}


async def test_three_plans_are_generated_checked_and_shown(tmp_path: Path) -> None:
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, RELAXED, CULTURE])
    out = await s.send("下周二去一天")
    assert out.kind == "itinerary"
    assert [p.label for p in out.round.plans] == ["经典必去", "轻松少走路", "深度文化"]
    assert all(p.shown for p in out.round.plans)
    assert [v.emphasis for v in out.versions] == list(ALL)
    assert all(v.validation.status == "passed" for v in out.versions), [v.validation.issues for v in out.versions]
    # 比较用的数字保存时就算好了
    assert out.versions[0].metrics is not None and out.versions[0].metrics.poiIds == ["a", "b"]
    assert "展示 3 份" in out.reply
    # 一份一份的提示词：侧重、节奏、候选不同
    assert "经典必去" in s.prompt(1) and '"id": "a"' in s.prompt(1) and '"mustVisit": true' in s.prompt(1)
    assert "轻松少走路" in s.prompt(2) and "节奏：轻松" in s.prompt(2)
    assert "深度文化" in s.prompt(3) and '"id": "c"' not in s.prompt(3)
    # 一轮存下来了，回复带着它
    assert s.rounds.get_round(out.round.id) is not None
    msg = s.conversations.messages(s.conv.id)[-1]
    assert msg.planningRoundId == out.round.id and msg.itineraryVersionId == out.versions[0].id
    assert s.stages == ["understanding", "selecting", "generating", "routing", "validating", "saving"]


async def test_near_duplicate_is_dropped_before_repair(tmp_path: Path) -> None:
    # 轻松的和经典的几乎一样（多了一个不存在的景点 zzz，算差 1 个；最后都是 13:55 离开），而且有错误：去掉，不花修正。
    # 钟点由程序推：zzz 08:00–08:30，a 等到 09:00 开门、待到 11:00；轻松那份走 12 分钟超过 10 分钟，坐地铁 20 分钟，b 11:30–13:55
    dup = plan([("zzz", "08:00", "08:30"), ("a", "09:00", "11:00"), ("b", "11:30", "13:55")])
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, dup, CULTURE], routes={("a", "b", "transit"): 20})
    out = await s.send("去")
    relaxed = by_emphasis(out)["relaxed"]
    assert not relaxed.shown and relaxed.removedReason.startswith("和「经典必去」几乎一样")
    # 去掉的也存成版本（以后对比要用）
    assert relaxed.versionId is not None and s.itineraries.get_version(relaxed.versionId) is not None
    assert len(s.model.calls) == 4  # 抽偏好 1 + 排行程 3，没有修正
    assert "「轻松少走路」没有展示" in out.reply and "展示 2 份" in out.reply


async def test_emphasis_rule_breaks_go_to_repair(tmp_path: Path) -> None:
    no_5a = plan([("b", "09:30", "11:30"), ("c", "13:30", "15:30")])
    s = setup(tmp_path, [prefs(**DATED), no_5a, RELAXED, CULTURE, CLASSIC], routes={("b", "c", "walk"): 10})
    out = await s.send("去")
    classic = out.versions[0]
    assert classic.emphasis == "classic" and classic.planner.rounds == 2
    assert classic.planner.firstRoundStatus == "failed"
    assert "5A 景点测试景点a没有排进去" in s.prompt(4)
    assert by_emphasis(out)["classic"].shown
    assert "修正过一次" in out.reply


async def test_still_failing_after_repair_is_not_shown(tmp_path: Path) -> None:
    short = plan([("a", "09:00", "10:00")])  # 深度文化要求停留不少于建议的 120 分钟
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, RELAXED, short, short])
    out = await s.send("去")
    culture = by_emphasis(out)["culture"]
    assert not culture.shown and culture.removedReason.startswith("没通过校验")
    assert out.kind == "itinerary" and "展示 2 份" in out.reply and "「深度文化」没有展示" in out.reply
    assert s.itineraries.get_version(culture.versionId).validation.status == "failed"  # type: ignore[union-attr]


async def test_one_model_error_drops_only_that_plan(tmp_path: Path) -> None:
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, LLMAuthError("测试：出错"), CULTURE])
    out = await s.send("去")
    relaxed = by_emphasis(out)["relaxed"]
    assert not relaxed.shown and relaxed.versionId is None and "模型没排出来" in relaxed.removedReason
    assert [v.emphasis for v in out.versions] == ["classic", "culture"]


async def test_all_model_errors_raise(tmp_path: Path) -> None:
    s = setup(tmp_path, [prefs(**DATED), LLMAuthError("测试"), LLMAuthError("测试"), LLMAuthError("测试")])
    with pytest.raises(LLMAuthError):
        await s.send("去")
    assert s.rounds.list_rounds(s.conv.id) == []


async def test_next_message_makes_a_new_round(tmp_path: Path) -> None:
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, RELAXED, CULTURE, prefs(**DATED), CLASSIC, RELAXED, CULTURE])
    first = await s.send("去")
    second = await s.send("再排一次")
    assert second.round.roundNumber == 2
    assert len(s.rounds.list_rounds(s.conv.id)) == 2
    # 同一侧重是同一份行程的下一个版本；旧的一轮还在
    assert [v.itineraryId for v in second.versions] == [v.itineraryId for v in first.versions]
    assert [v.versionNumber for v in second.versions] == [2, 2, 2]
    assert s.itineraries.get_version(first.versions[0].id) is not None
    assert "【上一版行程】" in s.prompt(5) and "经典" in s.prompt(5)


async def test_relaxed_rides_after_ten_minutes_walk(tmp_path: Path) -> None:
    # 走路 12 分钟：经典的走过去（默认 15 分钟以内走路），轻松的改坐地铁
    relaxed = plan([("a", "09:30", "11:30"), ("b", "12:30", "15:00")])
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, relaxed, CULTURE], routes={("a", "b", "transit"): 20})
    out = await s.send("去")
    classic_leg = out.versions[0].days[0].legs[0]
    relaxed_leg = out.versions[1].days[0].legs[0]
    assert classic_leg.route.mode == "walk"
    assert relaxed_leg.route.mode == "transit" and "10 分钟" in relaxed_leg.choice


async def test_relaxed_plan_says_its_own_pace(tmp_path: Path) -> None:
    # 用户没说节奏：三份共用"节奏：适中（按默认）"，但轻松那份实际按轻松排，要写清楚
    s = setup(tmp_path, [prefs(**DATED), CLASSIC, RELAXED, CULTURE])
    out = await s.send("去")
    classic, relaxed, culture = out.versions
    assert relaxed.frame.pace == "relaxed"
    assert not any("适中" in d for d in relaxed.defaultsUsed)
    assert any(d.startswith("节奏：轻松") and "轻松少走路" in d for d in relaxed.defaultsUsed)
    assert "节奏：适中（你没说，按默认）" in classic.defaultsUsed and "节奏：适中（你没说，按默认）" in culture.defaultsUsed
    # 一轮里记的是三份共用的
    assert "节奏：适中（你没说，按默认）" in out.round.defaultsUsed


async def test_relaxed_plan_mentions_user_pace_it_overrides(tmp_path: Path) -> None:
    s = setup(tmp_path, [prefs(**DATED, pace="intensive"), CLASSIC, RELAXED, CULTURE])
    out = await s.send("紧凑一点")
    relaxed = out.versions[1]
    line = next(d for d in relaxed.defaultsUsed if d.startswith("节奏："))
    assert "轻松" in line and "你说的是紧凑" in line
    # 其他两份照用户说的，不写节奏
    assert not any(d.startswith("节奏：") for d in out.versions[0].defaultsUsed)
