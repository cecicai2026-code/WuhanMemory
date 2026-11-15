"""保存下来的行程版本（板块 5）。前端类型在 packages/shared/src/itinerary.ts，两边要一致。

一个版本是一份快照：生成时的景点资料（名字、坐标、开放时间、预约、票价、支付，连同核实状态）、
程序查到的交通、校验结果和用的模型都存在里面。版本存下后不再修改，以后景点资料改了也不影响旧版本，
所以分享页（板块 7）可以绑定版本，双模型对比（板块 6）也能回头看当时的结果。

2026-07 骨架里的 MapPoi、RouteSegment 等旧结构已经删掉。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.planning import PlanDraft, TravelerPreferences, TripFrame, ValidationReport
from app.schemas.poi import Coordinates, OpeningHours, Payment, Reservation, Ticket
from app.schemas.poi_api import FactOut
from app.schemas.route import RouteOut


class StopFacts(BaseModel):
    """行程卡上用到的景点资料，由程序从景点库取，不让模型写。"""

    openingHours: FactOut[OpeningHours]
    reservation: FactOut[Reservation]
    ticket: FactOut[Ticket]
    payment: FactOut[Payment]
    recommendedDurationMinutes: FactOut[int]


class ItineraryStop(BaseModel):
    poiId: str
    name: str
    district: str
    category: str
    location: Coordinates
    arrive: str
    leave: str
    # 模型写的"为什么这样排"
    reason: str
    facts: StopFacts


class ItineraryLeg(BaseModel):
    """同一天相邻两站之间的交通。时间是程序向高德查的，不是模型说的。"""

    fromPoiId: str
    toPoiId: str
    route: RouteOut
    # 为什么选这种方式，例如"步行 12 分钟，走过去"、"没有公交方案，改步行"
    choice: str


class ItineraryDay(BaseModel):
    dayNumber: int
    # 日期未定时为 null
    date: date | None
    theme: str
    stops: list[ItineraryStop]
    legs: list[ItineraryLeg]


class PlannerInfo(BaseModel):
    provider: str  # qwen / doubao
    providerLabel: str
    # 对方返回的真实模型名
    model: str | None
    # 生成了几轮：1 是一次通过或没修正，2 是把错误交给模型修正过一次
    rounds: int
    # 第一轮的校验结果（修正过时，能看出改之前有哪些错误）
    firstRoundStatus: Literal["passed", "warning", "failed"]
    firstRoundErrors: int


class ItineraryVersionData(BaseModel):
    """一个版本的内容。存进 itinerary_versions.data_json。"""

    title: str
    city: str = "武汉"
    frame: TripFrame
    preferences: TravelerPreferences
    # 程序替用户补上的默认值，例如 ["节奏：适中（你没说，按默认）"]，界面上要写出来
    defaultsUsed: list[str] = Field(default_factory=list)
    days: list[ItineraryDay]
    validation: ValidationReport
    planner: PlannerInfo
    # 模型最后一轮的原始输出。没通过校验时 days 里可能缺了不存在的景点，原样留着给板块 6 对比
    draft: PlanDraft
    # 资料状态（过期、待确认）按哪一天算的
    dataAsOf: date


class ItineraryVersion(ItineraryVersionData):
    id: str
    itineraryId: str
    versionNumber: int
    createdAt: datetime
