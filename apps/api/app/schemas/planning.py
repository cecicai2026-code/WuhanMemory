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
