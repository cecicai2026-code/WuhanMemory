"""偏好：合并每条消息抽到的偏好、判断要不要反问、补默认值。

这些都由程序决定，不让模型自己决定要不要追问，规则是（2026-11-15 Cecilia 确认）：
- 天数必须有，没有就问。
- 日期问一次；用户说没定，或问过一次还是没说，就照样规划，校验时给"日期未定"的警告。
- 节奏、交通偏好没说就用默认值（适中、地铁公交优先），并在对话纸上写明"按默认"。
- 预算、同行人没说就不管，提示词里写"没说"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.schemas.planning import Pace, TransportPreference, TravelerPreferences, TripFrame

DEFAULT_PACE: Pace = "moderate"
DEFAULT_TRANSPORT: TransportPreference = "metro"

PACE_LABELS = {"relaxed": "轻松", "moderate": "适中", "intensive": "紧凑"}
TRANSPORT_LABELS = {"metro": "地铁公交优先", "walk": "尽量走路", "taxi": "打车"}
BUDGET_LABELS = {"low": "省钱", "medium": "适中", "high": "不太在意花费"}
PARTY_LABELS = {"solo": "一个人", "couple": "情侣", "friends": "朋友", "family": "带孩子", "elderly": "带老人"}


def merge(old: TravelerPreferences, new: TravelerPreferences) -> TravelerPreferences:
    """新抽到的盖过旧的；新的没说（空）的，保留旧的。模型被要求输出合并后的完整偏好，这里再兜一次底。"""
    merged = old.model_dump()
    for key, value in new.model_dump().items():
        if value is None or value == [] or (key == "dateUndecided" and value is False):
            continue
        merged[key] = value
    if new.startDate is not None:
        merged["dateUndecided"] = False
    return TravelerPreferences.model_validate(merged)


@dataclass
class Question:
    text: str
    asked: list[str]


def question_for(prefs: TravelerPreferences, already_asked: set[str], today: date) -> Question | None:
    """缺关键信息时返回要问的话，不缺返回 None。"""
    ask: list[str] = []
    parts: list[str] = []
    if prefs.days is None:
        ask.append("days")
        parts.append("还需要知道打算玩几天，才能排行程。" if "days" in already_asked else "打算玩几天？")
    date_open = prefs.startDate is None and not prefs.dateUndecided
    if date_open and "date" not in already_asked:
        ask.append("date")
        parts.append("哪天出发？还没定也可以，直接说没定。")
    elif prefs.startDate is not None and prefs.startDate < today and "past-date" not in already_asked:
        ask.append("past-date")
        parts.append(f"你说的出发日期 {prefs.startDate.isoformat()} 已经过去了，是哪一天？")
    if not ask:
        return None
    return Question(text="".join(parts), asked=ask)


@dataclass
class Frame:
    frame: TripFrame
    transport: TransportPreference
    defaults_used: list[str] = field(default_factory=list)


def frame_for(prefs: TravelerPreferences) -> Frame:
    assert prefs.days is not None, "没有天数时应该先反问"
    defaults: list[str] = []
    pace = prefs.pace
    if pace is None:
        pace = DEFAULT_PACE
        defaults.append(f"节奏：{PACE_LABELS[pace]}（你没说，按默认）")
    transport = prefs.transport
    if transport is None:
        transport = DEFAULT_TRANSPORT
        defaults.append(f"交通：{TRANSPORT_LABELS[transport]}（你没说，按默认）")
    if prefs.startDate is None:
        defaults.append("日期：没定（闭馆日没法校验）")
    return Frame(frame=TripFrame(days=prefs.days, startDate=prefs.startDate, pace=pace), transport=transport, defaults_used=defaults)
