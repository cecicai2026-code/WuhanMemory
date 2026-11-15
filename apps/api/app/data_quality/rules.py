"""数据质量规则里用到的常量。改这里的数值要同步改 docs/architecture/data-model.md。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

# 景点所在城市的时区，"今天"按武汉时间算
CITY_TZ = ZoneInfo("Asia/Shanghai")

# 武汉市范围的粗略矩形（GCJ-02 经纬度）。
# 武汉市域大约在东经 113°41′ 到 115°05′、北纬 29°58′ 到 31°22′，
# 四周再放宽 0.02 度，留出 GCJ-02 偏移和取整的余量。
# 这只能挡住明显填错的坐标（经纬度写反、少一位、填成别的城市），不能代替在地图上看一眼。
WUHAN_BOUNDS = {
    "min_lng": 113.66,
    "max_lng": 115.10,
    "min_lat": 29.95,
    "max_lat": 31.39,
}

# 会变的信息，以及过期时间的上限（天）：expiresAt 不能晚于 lastCheckedAt 加这个天数。
# 可以填得更早，例如节假日的临时开放时间写到假期结束那天。
VOLATILE_MAX_DAYS: dict[str, int] = {
    "operatingStatus": 90,
    "openingHours": 90,
    "reservation": 90,
    "ticket": 180,
    "payment": 180,
    "food": 180,
    "transport": 365,
}

# 不会变的单条信息。必须有来源和核实日期，不用填过期时间。
STABLE_FACTS = ("location", "address", "intro", "history", "recommendedDurationMinutes", "bestTime")

# 景点文件里必须出现的单条信息（没有资料也要写出来，标 verification: "todo"）
REQUIRED_FACTS = (
    "location",
    "address",
    "intro",
    "history",
    "openingHours",
    "ticket",
    "reservation",
    "payment",
    "transport",
    "recommendedDurationMinutes",
    "bestTime",
)

# 字段的中文名，报错时用
FIELD_LABELS: dict[str, str] = {
    "operatingStatus": "开放状态",
    "location": "坐标",
    "address": "地址",
    "intro": "简介",
    "history": "历史文化",
    "openingHours": "开放时间",
    "ticket": "票价",
    "reservation": "预约",
    "payment": "支付方式",
    "transport": "怎么去",
    "recommendedDurationMinutes": "建议游玩时长",
    "bestTime": "适合去的时段",
    "photoSpots": "拍照机位",
    "food": "周边美食",
}


def today_in_city() -> date:
    return datetime.now(CITY_TZ).date()
