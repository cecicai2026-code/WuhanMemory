"""规划链路的提示词。两个模型用同一套，板块 6 对比才公平。

网关会在系统提示词后面再加一句"只输出一个 JSON 对象……"，这里不用重复。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.planning import PlanDraft, PlanOutline, TravelerPreferences, TripFrame
from app.services.planning.interests import INTERESTS
from app.services.planning.preferences import PACE_LABELS
from app.services.planning.validate import DAY_EARLIEST, DAY_LATEST, DAY_LIMIT_MINUTES, TRANSPORT_SLACK_MINUTES, fmt

WEEKDAYS = "一二三四五六日"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def language_rule() -> str:
    """当前语言是英文时加在系统提示词后面：模型写给人看的字段用英文（中英双语，app/core/lang.py）。
    规则本身仍用中文写，两个模型看到的是同一套规则，只多这一句。"""
    from app.core.lang import current_lang

    if current_lang() != "en":
        return ""
    return "\n\n语言：用户用的是英文网站。title、theme、reason 一律用英文写（景点名可以用候选清单里给的名字）。"


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
- 你不写到达、离开的钟点。每天写一个出发时间 start（HH:MM，24 小时制，就是到达第一站的时间），每站写停留分钟数 stayMinutes。
- 钟点由程序推：后一站到达 = 前一站离开 + 【两站之间的真实交通】里的分钟数 + {TRANSPORT_SLACK_MINUTES} 分钟，往后取整到 5 分钟；到得比开门早就等到开门；离开 = 到达 + stayMinutes。排之前自己按这个推一遍，保证下面几条：
  - 每天最早 {fmt(DAY_EARLIEST)} 出发，最晚 {fmt(DAY_LATEST)} 离开最后一站；
  - 每天从第一站到达到最后一站离开的总时长不超过：轻松 {DAY_LIMIT_MINUTES['relaxed'] // 60} 小时，适中 {DAY_LIMIT_MINUTES['moderate'] // 60} 小时，紧凑 {DAY_LIMIT_MINUTES['intensive'] // 60} 小时（交通和等待都算在里面）；
  - 每站在最晚入场时间（lastEntry）之前到达、关门之前离开；不要排在闭馆日（closedWeekdays，1 是周一，7 是周日）。开放时间写"未知"的景点可以排，但尽量放在白天。
- 用【两站之间的真实交通】决定顺序和一天放几站：同一天尽量排在同一片区域（武昌、汉口、汉阳），少来回跨江，路上时间长的一天就少放几站。
- 你给出顺序后，程序会在每一天内部按【两站之间的真实交通】重新排列站点，让路上时间最少（只在不增加错误时才换；出发时间仍是到达新的第一站的时间）。所以你最要紧的是每天放哪几站、每站待多久、几点出发。
- stayMinutes 参考 recommendedDurationMinutes，"未知"的按景点类型估计。
- reason 用一两句中文说明为什么这样排（顺路、对得上哪个兴趣、什么时段去合适），不要写开放时间、票价、交通时间这些事实，这些由程序从景点库和高德取。
- 不写交通方式，程序会自己选。

输出格式：
{{"title": "武汉两日：老城历史与江边", "days": [{{"dayNumber": 1, "theme": "一句话主题", "start": "09:30", "stops": [{{"poiId": "候选里的 id", "stayMinutes": 120, "reason": "为什么这样排"}}]}}]}}"""


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
    transit: list[str],
    previous: BaseModel | None,
    emphasis: str | None = None,
) -> str:
    parts = [
        "【行程要求】",
        *_trip_lines(frame),
        f"交通偏好：{transport_label}",
        f"兴趣：{'、'.join(prefs.interests) or '没说'}",
        f"预算：{prefs.budget or '没说'}；同行：{prefs.party or '没说'}",
        f"其他要求：{prefs.notes or '没有'}",
        f"用户最新说的话：{message}",
        *(["", "【这份方案的侧重】", emphasis] if emphasis else []),
        "",
        "【候选景点】",
        _json(candidates),
        "",
        "【两站之间的真实交通】（程序会选的方式和高德查到的分钟数；↔ 表示来回一样，→ 是单程）",
        "；".join(transit),
    ]
    if previous is not None:
        parts += ["", "【上一版行程】这是同一侧重上一次排的，用户在它的基础上提了新要求，按新要求调整：", previous.model_dump_json()]
    return "\n".join(parts)


# ---------- 修正 ----------

REPAIR_SYSTEM = (
    GENERATE_SYSTEM
    + f"""

现在是修正环节：程序按你上一次给的出发时间和停留时长、以及程序按真实交通重排后的顺序推出了钟点，校验发现了下面列出的错误。
只改有错误的地方，其余安排尽量保持不变。你能改的是：出发时间 start、站点的顺序、停留时长 stayMinutes、换掉或去掉某一站、把某站挪到别的天。钟点照样由程序重新推。
输出修正后的完整行程，格式和上面一样。"""
)


def _scheduled_lines(draft: PlanDraft) -> list[str]:
    out = []
    for day in draft.days:
        out.append(f"第 {day.dayNumber} 天：" + "；".join(f"{s.poiId} {s.arrive}–{s.leave}" for s in day.stops))
    return out


def repair_user_prompt(
    *, generate_prompt: str, outline: PlanOutline, scheduled: PlanDraft, errors: list[str], legs: list[str]
) -> str:
    return "\n".join(
        [
            generate_prompt,
            "",
            "【你上一次排的行程】",
            outline.model_dump_json(),
            "",
            "【程序推出来的钟点】",
            *_scheduled_lines(scheduled),
            "",
            "【校验发现的错误】",
            *[f"- {e}" for e in errors],
            "",
            "【这几段用的真实交通时间】",
            *([f"- {leg}" for leg in legs] or ["- 没有"]),
        ]
    )
