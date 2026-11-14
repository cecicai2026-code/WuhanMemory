"""景点资料检查。

把 data/pois/*.json 逐个读进来，对照文书里的三条规则检查：
1. 每个景点必须有坐标（在武汉范围内）和记录在案的来源；
2. 会变的信息必须有核实日期和过期日期，过期了要报出来；
3. 每条信息要说明是实地核实、核对过来源、官网占位还是 TODO。
另外检查照片文件在不在。

问题分两级：
- error：数据不合格，不能导入数据库；
- warning：可以导入，但界面上要有标记或需要 Cecilia 处理（例如已过期）。

每个问题有一个 code，测试按 code 判断，不依赖中文说明的措辞。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.data_quality.rules import (
    FIELD_LABELS,
    REQUIRED_FACTS,
    VOLATILE_MAX_DAYS,
    WUHAN_BOUNDS,
)
from app.schemas.poi import Fact, OpeningHours, PoiFile

Level = Literal["error", "warning"]

ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass
class Issue:
    level: Level
    code: str
    poi_id: str
    field: str
    message: str

    def __str__(self) -> str:
        tag = "错误" if self.level == "error" else "警告"
        where = f"[{self.field}] " if self.field else ""
        return f"{tag} {self.poi_id} {where}{self.message}"


@dataclass
class Stats:
    pois: int = 0
    facts: int = 0
    onsite: int = 0
    confirmed: int = 0
    placeholder: int = 0
    todo: int = 0
    expired: int = 0
    own_photos: int = 0
    placeholder_photos: int = 0


@dataclass
class CheckReport:
    issues: list[Issue] = field(default_factory=list)
    # 通过结构检查的景点（可能还有 error，导入前要看 ok）
    pois: list[PoiFile] = field(default_factory=list)
    stats: Stats = field(default_factory=Stats)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self, poi_id: str | None = None) -> set[str]:
        return {i.code for i in self.issues if poi_id is None or i.poi_id == poi_id}


class _PoiChecker:
    def __init__(self, poi: PoiFile, data_dir: Path, today: date, report: CheckReport):
        self.poi = poi
        self.data_dir = data_dir
        self.today = today
        self.report = report
        self.sources = {s.id: s for s in poi.sources}

    # ---------- 记录问题 ----------

    def add(self, level: Level, code: str, field_name: str, message: str) -> None:
        self.report.issues.append(Issue(level, code, self.poi.id, field_name, message))

    def error(self, code: str, field_name: str, message: str) -> None:
        self.add("error", code, field_name, message)

    def warning(self, code: str, field_name: str, message: str) -> None:
        self.add("warning", code, field_name, message)

    # ---------- 总入口 ----------

    def run(self) -> None:
        self.report.stats.pois += 1
        self.check_basics()
        self.check_sources()

        for name in REQUIRED_FACTS:
            fact = getattr(self.poi, name)
            label = FIELD_LABELS[name]
            if fact is None:
                if name == "location":
                    self.error("missing-location", name, "缺坐标")
                else:
                    self.error(
                        "missing-field",
                        name,
                        f"缺少「{label}」。没有资料也要写出来，标 verification: \"todo\"",
                    )
                continue
            self.check_fact(name, label, fact, VOLATILE_MAX_DAYS.get(name))

        self.check_location()
        self.check_opening_hours()

        for i, fact in enumerate(self.poi.photoSpots):
            self.check_fact(f"photoSpots[{i}]", "拍照机位", fact, None)
        for i, fact in enumerate(self.poi.food):
            self.check_fact(f"food[{i}]", "周边美食", fact, VOLATILE_MAX_DAYS["food"])

        self.check_reviews()
        self.check_photos()

    # ---------- 基本信息和来源 ----------

    def check_basics(self) -> None:
        if not ID_PATTERN.match(self.poi.id):
            self.error("bad-id", "id", "id 只能用小写英文字母、数字和连字符，例如 yellow-crane-tower")
        for name, label in (("name", "名称"), ("district", "所在区"), ("category", "类别")):
            if not getattr(self.poi, name).strip():
                self.error("missing-basic", name, f"缺{label}")

    def check_sources(self) -> None:
        seen: set[str] = set()
        for s in self.poi.sources:
            where = f"sources.{s.id}"
            if s.id in seen:
                self.error("duplicate-source", where, f"来源 id「{s.id}」重复")
            seen.add(s.id)
            if not s.title.strip():
                self.error("bad-source", where, "来源缺标题")
            if s.type != "field-visit" and not s.url:
                self.error("bad-source", where, "不是实地走访的来源必须有链接")
            if s.accessedAt is None:
                what = "走访日期" if s.type == "field-visit" else "查阅日期"
                self.error("bad-source", where, f"来源缺{what}")
            elif s.accessedAt > self.today:
                self.error("future-date", where, f"来源的日期 {s.accessedAt} 在今天之后")

    # ---------- 单条信息 ----------

    def check_fact(self, path: str, label: str, fact: Fact[Any], max_days: int | None) -> None:
        stats = self.report.stats
        stats.facts += 1

        if fact.verification == "todo":
            stats.todo += 1
            if path == "location":
                self.error("missing-location", path, "缺坐标。坐标是必填项，不能写 TODO")
            if fact.value is not None:
                self.error(
                    "todo-with-value",
                    path,
                    f"「{label}」标了 todo 却有内容。有来源就改成对应的核实方式，没有就删掉内容",
                )
            if not fact.todo:
                self.warning("todo-without-note", path, f"「{label}」是 TODO，最好在 todo 里写明缺什么")
            return

        setattr(stats, fact.verification, getattr(stats, fact.verification) + 1)

        if fact.value is None:
            self.error("missing-value", path, f"「{label}」标了核实方式却没有内容")

        # 来源
        if not fact.sourceId:
            self.error("missing-source", path, f"「{label}」缺来源")
        elif fact.sourceId not in self.sources:
            self.error("unknown-source", path, f"「{label}」引用的来源「{fact.sourceId}」不在 sources 里")
        else:
            source = self.sources[fact.sourceId]
            if fact.verification == "onsite" and source.type != "field-visit":
                self.error(
                    "verification-source-mismatch",
                    path,
                    f"「{label}」标为实地核实，来源却不是实地走访",
                )
            if fact.verification in ("placeholder", "confirmed") and source.type == "field-visit":
                self.error(
                    "verification-source-mismatch",
                    path,
                    f"「{label}」来源是实地走访，核实方式应该是 onsite",
                )

        # 核实日期
        if fact.lastCheckedAt is None:
            self.error("missing-checked-at", path, f"「{label}」缺核实日期 lastCheckedAt")
        elif fact.lastCheckedAt > self.today:
            self.error("future-date", path, f"「{label}」的核实日期 {fact.lastCheckedAt} 在今天之后")

        # 过期日期，只对会变的信息
        if max_days is None:
            return
        if fact.expiresAt is None:
            self.error("missing-expires-at", path, f"「{label}」会变，必须有过期日期 expiresAt")
            return
        if fact.lastCheckedAt is not None:
            span = (fact.expiresAt - fact.lastCheckedAt).days
            if span <= 0:
                self.error("bad-expiry", path, f"「{label}」的过期日期不晚于核实日期")
            elif span > max_days:
                self.error(
                    "expiry-too-long",
                    path,
                    f"「{label}」的有效期 {span} 天，超过上限 {max_days} 天",
                )
        if fact.expiresAt < self.today:
            stats.expired += 1
            self.warning(
                "expired",
                path,
                f"「{label}」已过期（过期日期 {fact.expiresAt}），需要重新核实",
            )

    # ---------- 坐标和开放时间的内容 ----------

    def check_location(self) -> None:
        fact = self.poi.location
        if fact is None or fact.value is None:
            return
        v = fact.value
        b = WUHAN_BOUNDS
        if not (b["min_lng"] <= v.lng <= b["max_lng"] and b["min_lat"] <= v.lat <= b["max_lat"]):
            hint = "，经纬度可能写反了" if b["min_lng"] <= v.lat <= b["max_lng"] else ""
            self.error(
                "location-out-of-bounds",
                "location",
                f"坐标 ({v.lng}, {v.lat}) 不在武汉范围内{hint}",
            )

    def check_opening_hours(self) -> None:
        fact = self.poi.openingHours
        if fact is None or fact.value is None:
            return
        hours: OpeningHours = fact.value
        if not hours.allDay and not hours.periods:
            self.error("bad-opening-hours", "openingHours", "开放时间既不是全天开放，也没有开放时段")
        for d in hours.closedWeekdays:
            if not 1 <= d <= 7:
                self.error("bad-opening-hours", "openingHours", f"闭馆日 {d} 不在 1 到 7 之间")
        for i, p in enumerate(hours.periods):
            where = f"openingHours.periods[{i}]"
            times = {"open": p.open, "close": p.close, "lastEntry": p.lastEntry}
            bad = [k for k, t in times.items() if t is not None and not TIME_PATTERN.match(t)]
            for k in bad:
                self.error("bad-opening-hours", where, f"{k} 的时间「{times[k]}」要写成 08:30 这样")
            if not bad:
                if p.open >= p.close:
                    self.error("bad-opening-hours", where, "开门时间不早于关门时间")
                if p.lastEntry and not p.open <= p.lastEntry <= p.close:
                    self.error("bad-opening-hours", where, "最晚入场时间不在开放时段内")
            if any(not 1 <= d <= 7 for d in p.weekdays):
                self.error("bad-opening-hours", where, "weekdays 要用 1 到 7 表示周一到周日")
            if p.months and any(not 1 <= m <= 12 for m in p.months):
                self.error("bad-opening-hours", where, "months 要用 1 到 12")

    # ---------- 评价 ----------

    def check_reviews(self) -> None:
        for i, r in enumerate(self.poi.reviews):
            where = f"reviews[{i}]"
            if not r.author.strip():
                self.error("review-without-author", where, "评价必须署名")
            if not r.text.strip():
                self.error("bad-review", where, "评价没有内容")
            if r.visitedAt > self.today:
                self.error("future-date", where, f"评价的游玩日期 {r.visitedAt} 在今天之后")

    # ---------- 照片 ----------

    def check_photos(self) -> None:
        stats = self.report.stats
        own_dir = self.data_dir / "photos" / self.poi.id
        placeholder_dir = self.data_dir / "photos-placeholder" / self.poi.id
        listed: set[str] = set()

        for i, p in enumerate(self.poi.photos):
            where = f"photos[{i}]"
            if "/" in p.file or "\\" in p.file or p.file.startswith("."):
                self.error("bad-photo", where, f"文件名「{p.file}」只写文件名，不要带目录")
                continue
            if p.file in listed:
                self.error("bad-photo", where, f"照片「{p.file}」登记了两次")
            listed.add(p.file)
            if not p.caption.strip():
                self.error("bad-photo", where, f"照片「{p.file}」缺一句说明")

            if p.license == "official-placeholder":
                stats.placeholder_photos += 1
                if not p.sourceUrl or p.retrievedAt is None:
                    self.error(
                        "bad-photo",
                        where,
                        f"官网占位照片「{p.file}」必须写来源链接 sourceUrl 和下载日期 retrievedAt",
                    )
                if not (placeholder_dir / p.file).is_file():
                    # 占位照片不进 git，换台电脑就没有，所以只算警告
                    self.warning(
                        "placeholder-photo-missing",
                        where,
                        f"占位照片 data/photos-placeholder/{self.poi.id}/{p.file} 不在本机",
                    )
                continue

            stats.own_photos += 1
            if p.license == "own" and not p.author:
                self.error("bad-photo", where, f"照片「{p.file}」缺拍摄人 author")
            if p.license == "open-license" and (not p.sourceUrl or not p.licenseNote):
                self.error(
                    "bad-photo",
                    where,
                    f"授权图片「{p.file}」必须写来源链接 sourceUrl 和授权说明 licenseNote",
                )
            if not (own_dir / p.file).is_file():
                self.error(
                    "photo-missing",
                    where,
                    f"照片文件 data/photos/{self.poi.id}/{p.file} 不存在",
                )

        for i, fact in enumerate(self.poi.photoSpots):
            spot = fact.value
            if spot and spot.photo and spot.photo not in listed:
                self.error(
                    "bad-photo",
                    f"photoSpots[{i}]",
                    f"拍照机位的示例照片「{spot.photo}」没有在 photos 里登记",
                )

        if own_dir.is_dir():
            for f in sorted(own_dir.iterdir()):
                if f.is_file() and not f.name.startswith(".") and f.name not in listed:
                    self.warning(
                        "photo-not-listed",
                        "photos",
                        f"data/photos/{self.poi.id}/{f.name} 没有在 photos 里登记",
                    )


def _validation_issues(poi_id: str, err: ValidationError) -> list[Issue]:
    issues = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        issues.append(Issue("error", "bad-format", poi_id, loc, f"格式不对：{e['msg']}"))
    return issues


def check_poi_dict(raw: Any, *, file_stem: str, data_dir: Path, today: date, report: CheckReport) -> None:
    """检查一个景点文件的内容，结果写进 report。"""
    poi_id = raw.get("id", file_stem) if isinstance(raw, dict) else file_stem
    try:
        poi = PoiFile.model_validate(raw)
    except ValidationError as err:
        report.issues.extend(_validation_issues(str(poi_id), err))
        return
    if poi.id != file_stem:
        report.issues.append(
            Issue("error", "id-filename-mismatch", poi.id, "id", f"id「{poi.id}」和文件名「{file_stem}.json」不一致")
        )
    _PoiChecker(poi, data_dir, today, report).run()
    report.pois.append(poi)


def check_data_dir(data_dir: Path, today: date) -> CheckReport:
    """检查 data_dir/pois/ 下的全部景点文件。"""
    report = CheckReport()
    pois_dir = data_dir / "pois"
    files = sorted(pois_dir.glob("*.json")) if pois_dir.is_dir() else []
    seen: dict[str, str] = {}

    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            report.issues.append(Issue("error", "bad-json", path.stem, "", f"不是合法的 JSON：{err}"))
            continue
        before = len(report.pois)
        check_poi_dict(raw, file_stem=path.stem, data_dir=data_dir, today=today, report=report)
        if len(report.pois) > before:
            poi_id = report.pois[-1].id
            if poi_id in seen:
                report.issues.append(
                    Issue("error", "duplicate-id", poi_id, "id", f"id 和 {seen[poi_id]} 重复")
                )
            seen[poi_id] = path.name

    return report
