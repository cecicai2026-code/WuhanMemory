"""规划链路的提示词。两个模型用同一套，板块 6 对比才公平。

网关会在系统提示词后面再加一句"只输出一个 JSON 对象……"，这里不用重复。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.schemas.planning import PlanDraft, TravelerPreferences, TripFrame
from app.services.planning.interests import INTERESTS
from app.services.planning.preferences import PACE_LABELS
from app.services.planning.validate import DAY_EARLIEST, DAY_LATEST, DAY_LIMIT_MINUTES, TRANSPORT_SLACK_MINUTES, fmt

WEEKDAYS = "一二三四五六日"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# ---------- 抽偏好 ----------

EXTRACT_SYSTEM = f"""你是武汉旅行规划助手的"需求理解"环节。你的任务只有一个：从用户的话里抽出旅行偏好，填进固定的 JSON 结构。

规则：
- 只填用户说了的，没说的保持 null 或空列表，不要猜。
- 会给你"之前已经知道的偏好"。用户这次没提到的，原样保留；这次改了的，用新的。输出合并后的完整偏好。
- days：玩几天（整数）。"周末"算 2 天。
- startDate：第一天的日期，YYYY-MM-DD。只有用户说了具体日期，或"下周六""国庆第一天"这类能换算的说法才填；换算时以给你的"今天"为准。
- dateUndecided：用户明确说日期还没定、随便哪天，填 true。
- pace：relaxed（轻松、慢慢逛、不想太累）/ moderate（适中）/ intensive（紧凑、多去几个地方）。
- interests：只能从这几个里选：{"、".join(INTERESTS)}。用户说的其他兴趣写进 notes。
- budget：low / medium / high。party：solo / couple / friends / family（带孩子）/ elderly（带老人）。
- transport：metro（地铁、公交）/ walk（多走路、步行）/ taxi（打车、开车）。
- mustVisit / avoid：用户点名想去 / 不想去的地方，写原话里的名字。
- notes：其他要求，一句话。

输出格式：
{{"days": 2, "startDate": null, "dateUndecided": false, "pace": null, "interests": ["历史文化"], "budget": null, "party": null, "transport": "metro", "mustVisit": [], "avoid": [], "notes": null}}"""


def extract_user_prompt(message: str, previous: TravelerPreferences, today: date) -> str:
    return (
        f"今天是 {today.isoformat()}（周{WEEKDAYS[today.weekday()]}）。\n"
        f"之前已经知道的偏好：{previous.model_dump_json()}\n"
        f"用户这次说：{message}"
    )


# ---------- 生成行程 ----------

GENERATE_SYSTEM = f"""你是武汉旅行规划助手的"排行程"环节。根据用户偏好，从给你的候选景点里挑景点，排出逐日行程。

必须遵守：
- 只能用候选清单里的景点，用它的 id 引用（poiId）。不能编造清单以外的地方，也不要写餐馆、酒店。
- 每个景点整份行程里只出现一次。标了 mustVisit 的一定要排进去。
- 天数必须正好等于要求的天数，dayNumber 从 1 开始。
- 时间用 24 小时制 HH:MM。arrive 是到达时间，leave 是离开时间。
- 每天最早 {fmt(DAY_EARLIEST)} 到达第一站，最晚 {fmt(DAY_LATEST)} 离开最后一站。
- 每天从第一站到达到最后一站离开的总时长不超过：轻松 {DAY_LIMIT_MINUTES['relaxed'] // 60} 小时，适中 {DAY_LIMIT_MINUTES['moderate'] // 60} 小时，紧凑 {DAY_LIMIT_MINUTES['intensive'] // 60} 小时。
- 到达和离开都要在开放时间内，到达不能晚于最晚入场时间（lastEntry），不要排在闭馆日（closedWeekdays，1 是周一，7 是周日）。开放时间写"未知"的景点可以排，但尽量放在白天。
- 相邻两站之间要留出交通时间：程序会用高德查真实的交通时间来校验，空档短于真实时间就算错。给了两两之间的直线距离做参考，实际路程比直线长，地铁还要换乘和步行进出站，宁可多留；在估计的交通时间之外再多留 {TRANSPORT_SLACK_MINUTES} 分钟余量。
- 停留时间参考 recommendedDurationMinutes，"未知"的按景点类型估计。
- 同一天尽量排在同一片区域（武昌、汉口、汉阳），少来回跨江。
- reason 用一两句中文说明为什么这样排（顺路、对得上哪个兴趣、什么时段去合适），不要写开放时间、票价、交通时间这些事实，这些由程序从景点库和高德取。
- 不写交通方式，程序会自己选。

输出格式：
{{"title": "武汉两日：老城历史与江边", "days": [{{"dayNumber": 1, "theme": "一句话主题", "stops": [{{"poiId": "候选里的 id", "arrive": "09:30", "leave": "11:30", "reason": "为什么这样排"}}]}}]}}"""


def _trip_lines(frame: TripFrame) -> list[str]:
    lines = [f"天数：{frame.days} 天", f"节奏：{PACE_LABELS[frame.pace]}"]
    if frame.startDate is None:
        lines.append("日期：还没定（避开闭馆日这条无法确认，尽量不要排在常见的周一闭馆景点上）")
    else:
        for i in range(frame.days):
            d = date.fromordinal(frame.startDate.toordinal() + i)
            lines.append(f"第 {i + 1} 天：{d.isoformat()}（周{WEEKDAYS[d.weekday()]}，{d.month} 月）")
    return lines


def generate_user_prompt(
    *,
    message: str,
    prefs: TravelerPreferences,
    frame: TripFrame,
    transport_label: str,
    candidates: list[dict[str, Any]],
    distances: list[str],
    previous: PlanDraft | None,
) -> str:
    parts = [
        "【行程要求】",
        *_trip_lines(frame),
        f"交通偏好：{transport_label}",
        f"兴趣：{'、'.join(prefs.interests) or '没说'}",
        f"预算：{prefs.budget or '没说'}；同行：{prefs.party or '没说'}",
        f"其他要求：{prefs.notes or '没有'}",
        f"用户最新说的话：{message}",
        "",
        "【候选景点】",
        _json(candidates),
        "",
        "【两两直线距离】",
        "；".join(distances),
    ]
    if previous is not None:
        parts += ["", "【上一版行程】用户在上一版的基础上提了新要求，按新要求调整：", previous.model_dump_json()]
    return "\n".join(parts)


# ---------- 修正 ----------

REPAIR_SYSTEM = (
    GENERATE_SYSTEM
    + """

现在是修正环节：程序校验了你上一次排的行程，发现了下面列出的错误。只改有错误的地方，其余安排尽量保持不变。
程序查到的真实交通时间也给你了，按它留空档。输出修正后的完整行程，格式和上面一样。"""
)


def repair_user_prompt(*, generate_prompt: str, draft: PlanDraft, errors: list[str], legs: list[str]) -> str:
    return "\n".join(
        [
            generate_prompt,
            "",
            "【你上一次排的行程】",
            draft.model_dump_json(),
            "",
            "【校验发现的错误】",
            *[f"- {e}" for e in errors],
            "",
            "【程序查到的真实交通时间】",
            *([f"- {leg}" for leg in legs] or ["- 没有"]),
        ]
    )
