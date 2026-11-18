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

from app.schemas.planning import PlanDraft, PlanOutline, TravelerPreferences, TripFrame, ValidationReport
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


class StopTicket(BaseModel):
    """一站的门票（每人）。日期未定时黄鹤楼夜场是"120 或 150 元"这种范围，所以有最低和最高。"""

    dayNumber: int
    poiId: str
    name: str
    # 都为 null 表示资料里没有票价（"不详"）
    minCny: float | None
    maxCny: float | None
    # 程序写的说明，例如 "免费"、"日场全票 70 元"、"夜场成人票 120 或 150 元（日期未定）"、"不详"
    label: str


class DayMetrics(BaseModel):
    dayNumber: int
    stopCount: int
    # 最后一站离开的时间；这天没有景点时为 null
    end: str | None
    transportMinutes: int
    walkingMeters: int
    # 步行距离不知道的段数（交通没查到，或旧缓存里没有换乘步行距离）
    walkingUnknownLegs: int


class PlanMetrics(BaseModel):
    """一份方案的数字，全部由程序从行程快照算出来，不用模型说的。"""

    poiIds: list[str]
    poiNames: list[str]
    stopCount: int
    # 查到了的交通时间合计，以及按方式分开：walk 步行、transit 公交地铁、drive 打车
    transportMinutes: int
    minutesByMode: dict[str, int]
    # 同一天相邻两站之间、没查到交通的段数（这些段的时间没算进去）
    unknownLegs: int
    # 步行段的距离 + 公交地铁段的换乘步行距离
    walkingMeters: int
    walkingUnknownLegs: int
    # 门票：每人、成人日场全票，免费的算 0
    tickets: list[StopTicket]
    ticketMinCny: float
    ticketMaxCny: float
    # 有一站票价不详就是 false，总价要标"不完整"
    ticketComplete: bool
    validationStatus: Literal["passed", "warning", "failed"]
    errorCount: int
    warningCount: int
    rounds: int
    days: list[DayMetrics]


class ComparisonRow(BaseModel):
    """对比表的一行：每份方案一格。texts 是程序写好的显示文字，values 是用来排序或画图的数（没有时为 null）。"""

    key: str
    label: str
    texts: list[str]
    values: list[float | None]
    note: str | None = None


class PlanComparison(BaseModel):
    # 每份方案的名字，例如 ["经典必去", "深度文化"]
    labels: list[str]
    rows: list[ComparisonRow]


class DayOrder(BaseModel):
    """一天的站点顺序：模型给的和程序按真实交通时间重排后的（ADR 0010）。"""

    dayNumber: int
    modelOrder: list[str]
    order: list[str]
    # 相邻两站交通分钟数之和；模型顺序里有一段没查到时为 null
    modelTransportMinutes: int | None
    transportMinutes: int | None
    changed: bool
    # shorter 换了；already-shortest 模型的顺序已经最省；more-errors 更省的顺序都会多出错误；
    # too-few-stops 不到 2 站；too-many-stops 超过 8 站没穷举；invalid-stops 有不在候选里或重复的站；travel-unknown 交通没查到
    reason: Literal[
        "shorter", "already-shortest", "more-errors", "too-few-stops", "too-many-stops", "invalid-stops", "travel-unknown"
    ]


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
    # 板块 5B：这份方案的侧重（classic 经典必去 / relaxed 轻松少走路 / culture 深度文化）；之前存的版本为 null
    emphasis: str | None = None
    # 程序算的数字，比较方案用；之前存的版本为 null
    metrics: PlanMetrics | None = None
    # 板块 6：第一版的完整校验报告和模型第一版的原始输出（修正过时和最终版不同）。之前存的版本为 null
    firstValidation: ValidationReport | None = None
    firstDraft: PlanDraft | None = None
    # 板块 6C：模型给的行程（出发时间、顺序、停留时长），draft 是程序从它推出钟点后的样子。之前存的版本为 null
    outline: PlanOutline | None = None
    firstOutline: PlanOutline | None = None
    # ADR 0010：每天的顺序由程序按真实交通时间重排。outline 是模型原样给的顺序，draft 和 days 是重排后的。之前存的版本为 null
    routeOrder: list[DayOrder] | None = None
    firstRouteOrder: list[DayOrder] | None = None


class ItineraryVersion(ItineraryVersionData):
    id: str
    itineraryId: str
    versionNumber: int
    createdAt: datetime


class RoundPlan(BaseModel):
    """一轮里的一份方案。"""

    emphasis: str
    label: str
    # 模型调用出错、没排出来时为 null
    itineraryId: str | None
    versionId: str | None
    shown: bool
    # 不展示的原因（几乎一样、没通过校验、模型出错），给用户看的话
    removedReason: str | None = None


class PlanningRoundData(BaseModel):
    """一次规划产生一轮：同一个请求按三种侧重排的几份方案（板块 5B）。再发消息就是新的一轮，旧的保留。"""

    conversationId: str
    roundNumber: int
    provider: str
    providerLabel: str
    # 按"经典必去 → 轻松少走路 → 深度文化"的顺序
    plans: list[RoundPlan]
    # 程序替用户补上的默认值，三份共用
    defaultsUsed: list[str] = Field(default_factory=list)


class PlanningRound(PlanningRoundData):
    id: str
    createdAt: datetime


class PlanningRoundOut(PlanningRound):
    """接口返回的一轮：附上展示的几份方案的版本和比较表。"""

    versions: list[ItineraryVersion]
    comparison: PlanComparison | None
