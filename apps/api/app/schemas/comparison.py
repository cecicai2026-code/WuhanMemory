"""双模型并排对比（板块 6）的数据结构。前端类型在 packages/shared/src/comparison.ts，两边要一致。

同一个请求、同一份偏好、同一份候选、同一种侧重，交给两个模型各排一份；下面的数字全部由程序算，
不让一个模型给另一个模型打分，也不写"哪个更好"。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.itinerary import ComparisonRow, PlanMetrics
from app.schemas.planning import TravelerPreferences


class CallStats(BaseModel):
    """这一边的模型调用，从网关的调用记录（llm_calls）汇总。"""

    # 网关调用次数（排行程 1 次、修正 0 或 1 次；抽偏好两边共用，不算在任何一边）
    callCount: int
    # 实际向模型发出的请求次数：重试、输出不合格让模型重答都算
    requestCount: int
    failedCalls: int
    retriedCalls: int
    # 输出不合格、让模型重答过的调用次数（网关的"修复"，不是行程的修正）
    reaskedCalls: int
    # 每次调用的耗时加起来（毫秒）
    modelMs: int
    # 对方返回了 token 数的调用加起来；一次都没返回时为 null
    inputTokens: int | None
    outputTokens: int | None
    # 没返回 token 数的调用次数
    tokensUnknownCalls: int
    # 每种用途调用了几次，例如 {"generate_itinerary": 1, "repair_itinerary": 1}
    byTask: dict[str, int] = Field(default_factory=dict)


class QualityMetrics(BaseModel):
    """一份行程的校验情况。"通过"指没有错误：现在景点资料全是占位，任何行程都有警告，按零警告算就永远不通过。"""

    firstPassed: bool
    firstStatus: Literal["passed", "warning", "failed"]
    firstErrorCount: int
    firstWarningCount: int
    # 第一版每种错误几条，例如 {"overlap": 2, "closed-day": 1}
    firstErrorCodes: dict[str, int]
    # 第一版有错误，交给模型修正过一次
    repaired: bool
    finalPassed: bool
    finalStatus: Literal["passed", "warning", "failed"]
    finalErrorCount: int
    finalWarningCount: int
    finalErrorCodes: dict[str, int]
    # 编造的景点：第一版里 id 在整个景点库里都找不到的
    firstFabricatedPoiIds: list[str]
    # 候选以外的景点：在景点库里，但这次不能用（用户说不去、暂停开放、这种侧重没给）
    firstOffListPoiIds: list[str]
    finalFabricatedPoiIds: list[str]
    finalOffListPoiIds: list[str]


class SideResult(BaseModel):
    """对比的一边：一个模型排的一份行程和它的数字。"""

    provider: str
    providerLabel: str
    # 对方返回的真实模型名
    model: str | None = None
    versionId: str | None = None
    # 模型没排出来（超时、额度等）时的说明；这时 quality 和 plan 为 null
    error: str | None = None
    quality: QualityMetrics | None = None
    plan: PlanMetrics | None = None
    calls: CallStats
    # 这一边从开始排到校验完的总时间（含查交通），毫秒
    wallMs: int


class PoiRef(BaseModel):
    poiId: str
    name: str


class DayDiff(BaseModel):
    dayNumber: int
    # 两边这一天的景点，按顺序；第一个是左边
    orders: list[list[PoiRef]]
    # 两边这一天都有的景点，按左边的顺序
    common: list[PoiRef]
    # 都有的景点先后顺序是否一样；都有的不到 2 个时为 null
    sameOrder: bool | None


class MovedPoi(BaseModel):
    """两边都用了，但排在不同的天。"""

    poiId: str
    name: str
    # 每一边排在第几天，第一个是左边
    days: list[int]


class PlanDiff(BaseModel):
    onlyLeft: list[PoiRef]
    onlyRight: list[PoiRef]
    both: list[PoiRef]
    days: list[DayDiff]
    moved: list[MovedPoi]
    # 两份几乎一样时的说明（5B 的判断：景点只差 0 或 1 个、每天结束时间相差不到 1 小时），不一样为 null
    nearDuplicate: str | None


class ComparisonTable(BaseModel):
    labels: list[str]
    rows: list[ComparisonRow]


class ModelComparisonData(BaseModel):
    """一次对比。存进 model_comparisons.data_json。"""

    request: str
    preferences: TravelerPreferences
    # 偏好是哪里来的：页面上由一个模型抽一次、两边共用；批量评测是手写的
    preferencesSource: Literal["extracted", "given"]
    # 抽偏好用的模型（preferencesSource 是 given 时为 null）
    extractor: str | None = None
    extractorCalls: CallStats | None = None
    emphasis: str
    emphasisLabel: str
    defaultsUsed: list[str] = Field(default_factory=list)
    # 两边，第一个是左边（千问），第二个是右边（豆包）
    sides: list[SideResult]
    # 两边都排出来时才有
    diff: PlanDiff | None = None
    table: ComparisonTable
    # 批量评测时是请求的 id，例如 "r01"；页面上发起的为 null
    evalRequestId: str | None = None


class ModelComparison(ModelComparisonData):
    id: str
    createdAt: datetime


class SideBrief(BaseModel):
    providerLabel: str
    model: str | None
    error: bool
    # 模型没排出来时为 null
    firstPassed: bool | None
    finalPassed: bool | None


class ModelComparisonSummary(BaseModel):
    """历史列表里的一条。"""

    id: str
    createdAt: datetime
    request: str
    emphasisLabel: str
    evalRequestId: str | None
    sides: list[SideBrief]
