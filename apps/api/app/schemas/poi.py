"""景点资料的数据格式（data/pois/*.json）。

每个景点一个 JSON 文件，由 Cecilia 核实后提交到 git。格式说明见
docs/architecture/data-model.md。

这里的模型只管"字段是什么类型"。哪些字段必填、来源和日期对不对、
有没有过期，由 app/data_quality/checker.py 检查，这样可以一次报出所有问题，
并给出中文的说明。所以下面很多字段是可选的，并不代表可以不填。
"""

from __future__ import annotations

from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# 这条信息是怎么来的
#   onsite      Cecilia 实地核实过
#   confirmed   Cecilia 核对过官网或售票页面，没在现场核实
#   placeholder Claude 按官网先填的占位，待 Cecilia 确认
#   todo        找不到可靠来源，写 TODO(Cecilia)
Verification = Literal["onsite", "confirmed", "placeholder", "todo"]

SourceType = Literal[
    "field-visit",  # Cecilia 实地走访
    "official-site",  # 景点官网
    "official-wechat",  # 景点官方公众号
    "official-ticketing",  # 官方售票或预约页面（小程序等）
    "government",  # 政府网站（区政府、文旅局、景区管委会），用于没有自己官网的街区
    "amap",  # 高德地图（坐标拾取器、地点搜索）
    "other",
]

CoordSystem = Literal["GCJ-02"]

T = TypeVar("T")


class _Model(BaseModel):
    # 写错字段名要能查出来，不能悄悄忽略
    model_config = ConfigDict(extra="forbid")


class Source(_Model):
    """一个来源。景点文件开头列出全部来源，各条信息用 sourceId 引用。"""

    id: str
    type: SourceType
    title: str
    url: str | None = None
    # 查阅日期；实地走访就是去的那天
    accessedAt: date | None = None


class Fact(_Model, Generic[T]):
    """一条信息，带来源、核实方式和日期。"""

    value: T | None = None
    verification: Verification
    sourceId: str | None = None
    lastCheckedAt: date | None = None
    # 会变的信息必须有；不会变的信息不用填
    expiresAt: date | None = None
    # verification 为 todo 时，写明缺什么，例如 "TODO(Cecilia): 官网没有写学生票"
    todo: str | None = None
    note: str | None = None


# ---------- 各条信息的内容 ----------


class Coordinates(_Model):
    lng: float
    lat: float
    coordSystem: CoordSystem


class OpeningPeriod(_Model):
    """一个开放时段。months 为空表示全年。weekdays 用 1 到 7 表示周一到周日。"""

    months: list[int] | None = None
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    open: str  # "08:30"
    close: str  # "17:30"
    lastEntry: str | None = None


class OpeningHours(_Model):
    # 街区、江滩这类全天开放的地方
    allDay: bool = False
    periods: list[OpeningPeriod] = Field(default_factory=list)
    # 每周固定闭馆的日子，1 到 7
    closedWeekdays: list[int] = Field(default_factory=list)
    # 例如 "周一闭馆，法定节假日除外"
    note: str | None = None


class TicketItem(_Model):
    name: str  # "成人票"
    priceCny: float


class Ticket(_Model):
    free: bool = False
    items: list[TicketItem] = Field(default_factory=list)
    note: str | None = None


class Reservation(_Model):
    required: bool
    how: str | None = None  # 在哪预约
    advanceDays: int | None = None
    note: str | None = None


PaymentMethod = Literal["wechat", "alipay", "cash", "foreign-card", "other"]


class Payment(_Model):
    methods: list[PaymentMethod] = Field(default_factory=list)
    note: str | None = None


class MetroAccess(_Model):
    station: str
    line: str | None = None
    exit: str | None = None
    walkMinutes: int | None = None


class Transport(_Model):
    metro: list[MetroAccess] = Field(default_factory=list)
    note: str | None = None


class PhotoSpot(_Model):
    title: str
    description: str
    # 示例照片，对应 photos 里的 file
    photo: str | None = None


class FoodItem(_Model):
    name: str
    walkMinutes: int | None = None
    note: str | None = None


ReviewRelation = Literal["self", "friend"]


class Review(_Model):
    """去过的人说。只用 Cecilia 和试用过的朋友写的，必须署名。"""

    author: str
    relation: ReviewRelation
    visitedAt: date
    text: str


PhotoLicense = Literal[
    "own",  # Cecilia 自己拍的，放 data/photos/<id>/，提交到 git
    "open-license",  # 可自由使用授权的图片，放 data/photos/<id>/，必须写授权说明
    "official-placeholder",  # 官网照片占位，放 data/photos-placeholder/<id>/，不提交
]


class Photo(_Model):
    file: str
    # 给看不到图的人读的一句话
    caption: str
    license: PhotoLicense
    author: str | None = None
    takenAt: date | None = None
    # 不是自己拍的照片必须有
    sourceUrl: str | None = None
    retrievedAt: date | None = None
    licenseNote: str | None = None


class PoiFile(_Model):
    """data/pois/<id>.json 的完整内容。"""

    schemaVersion: Literal[1] = 1
    id: str
    name: str
    district: str
    category: str
    tags: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

    location: Fact[Coordinates] | None = None
    address: Fact[str] | None = None
    intro: Fact[str] | None = None
    history: Fact[str] | None = None

    openingHours: Fact[OpeningHours] | None = None
    ticket: Fact[Ticket] | None = None
    reservation: Fact[Reservation] | None = None
    payment: Fact[Payment] | None = None
    transport: Fact[Transport] | None = None

    recommendedDurationMinutes: Fact[int] | None = None
    bestTime: Fact[str] | None = None

    photoSpots: list[Fact[PhotoSpot]] = Field(default_factory=list)
    food: list[Fact[FoodItem]] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    photos: list[Photo] = Field(default_factory=list)
