"""规划链路里传的数据结构（板块 5）。

- `PlanDraft`：模型按固定结构输出的行程草稿。模型只写"每天去哪些景点（用 id）、几点到几点、为什么"，
  不写日期、交通、开放时间、预约和支付：这些由程序从景点库和高德取。
- `ValidationReport`：`validate_itinerary` 的结果。

字段说明见 docs/architecture/ai-planning-pipeline.md。
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Pace = Literal["relaxed", "moderate", "intensive"]


Budget = Literal["low", "medium", "high"]
Party = Literal["solo", "couple", "friends", "family", "elderly"]
# 交通偏好：metro 地铁公交优先，walk 尽量走路，taxi 打车
TransportPreference = Literal["metro", "walk", "taxi"]


class TravelerPreferences(BaseModel):
    """模型从对话里抽出来的偏好。没说的留空，不猜；程序决定要不要反问、哪些用默认值。"""

    days: int | None = Field(default=None, ge=1, le=14)
    # 第一天的日期，只有用户说了具体日期（或能换算的说法，如"下周六"）才填
    startDate: date | None = None
    # 用户明确说日期还没定
    dateUndecided: bool = False
    pace: Pace | None = None
    interests: list[str] = Field(default_factory=list)
    budget: Budget | None = None
    party: Party | None = None
    transport: TransportPreference | None = None
    # 用户点名想去 / 不想去的地方，原话里的名字
    mustVisit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    # 其他要求，例如"不想早起""带老人少爬楼梯"
    notes: str | None = None


class PlanStop(BaseModel):
    poiId: str
    # "HH:MM"，到达和离开这个景点的时间。格式由 validate_itinerary 检查，这里不限制，
    # 这样格式错也能作为一条具体错误交给模型修正。
    arrive: str
    leave: str
    reason: str = ""


class PlanDay(BaseModel):
    dayNumber: int
    theme: str = ""
    stops: list[PlanStop] = Field(default_factory=list)


class PlanDraft(BaseModel):
    """模型输出的行程草稿。"""

    title: str = ""
    days: list[PlanDay] = Field(default_factory=list)


class TripFrame(BaseModel):
    """校验时要用到的用户要求：几天、哪天开始、什么节奏。"""

    days: int
    # 日期未定时为 None，闭馆日就没法校验，会给警告
    startDate: date | None = None
    pace: Pace = "moderate"


IssueLevel = Literal["error", "warning"]
ValidationStatus = Literal["passed", "warning", "failed"]


class ValidationIssue(BaseModel):
    level: IssueLevel
    # 机器读的类型，例如 closed-day、hours-unknown。全部取值见 ai-planning-pipeline.md
    code: str
    # 给人读的中文说明，写明是哪个景点、哪一项、为什么
    message: str
    dayNumber: int | None = None
    poiId: str | None = None
    # 依据的是景点的哪几项资料，例如 ["openingHours"]；界面用它在那一站旁边做标记
    fields: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    status: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]
