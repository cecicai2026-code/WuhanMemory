"""规划链路：一条用户消息进来，到反问、一轮方案或明确的失败说明出去。

    ① 抽偏好（模型） → ② 缺天数/日期就反问（程序） → ③ 筛候选，再按三种侧重各自调整（程序）
    → ④ 三份同时生成（模型，并行） → ⑤ 查相邻两站的真实交通（程序，高德，一个一个查）
    → ⑥ validate_itinerary + 侧重的额外规则（程序） → ⑦ 几乎一样的去掉（程序）
    → ⑧ 有错误的把具体错误交给模型修正一次（并行），再做 ⑤ ⑥ ⑦ → ⑨ 每份存成一个版本，记下这一轮（程序）

模型只做两件事：听懂用户的话，在候选里挑景点排时间。三种侧重的候选、节奏和规则由程序先定（emphasis.py），
景点资料、交通时间由程序从景点库和高德取；方案能不能给用户看由校验决定，比较用的数字由程序算（metrics.py）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.planning_round_repository import PlanningRoundRepository
from app.repositories.poi_repository import PoiRepository
from app.schemas.itinerary import (
    ItineraryDay,
    ItineraryLeg,
    ItineraryStop,
    ItineraryVersion,
    ItineraryVersionData,
    PlannerInfo,
    PlanningRound,
    PlanningRoundData,
    RoundPlan,
    StopFacts,
)
from app.schemas.planning import PlanDraft, TravelerPreferences, TripFrame, ValidationReport
from app.schemas.poi import Fact, PoiFile
from app.schemas.poi_api import SourceOut
from app.services.llm.errors import LLMError
from app.services.llm.gateway import LLMGateway
from app.services.planning import prompts
from app.services.planning.candidates import Candidates, candidate_brief, distance_table, select_candidates
from app.services.planning.emphasis import EMPHASES, Emphasis, candidates_for, check_emphasis, emphasis_frame, merge_issues, walk_limit
from app.services.planning.metrics import near_duplicate, plan_metrics
from app.services.planning.preferences import PACE_LABELS, TRANSPORT_LABELS, Frame, frame_for, merge, question_for
from app.services.planning.transport import MODE_LABELS, choose_leg
from app.services.planning.validate import day_date, validate_itinerary
from app.services.poi_view import fact_status
from app.services.routing.service import RouteService

# 界面上显示的规划步骤。顺序就是链路的顺序；repairing 只在第一轮有错误时出现。
Stage = Literal["understanding", "selecting", "generating", "routing", "validating", "repairing", "saving"]
STAGE_LABELS: dict[str, str] = {
    "understanding": "理解需求",
    "selecting": "从景点库挑候选",
    "generating": "模型排三份方案",
    "routing": "查真实交通时间",
    "validating": "校验",
    "repairing": "把错误交给模型修正",
    "saving": "保存",
}

DEFAULT_EMPHASES: tuple[str, ...] = tuple(EMPHASES)

OnStage = Callable[[str], Awaitable[None] | None]


@dataclass
class PlanOutcome:
    kind: Literal["question", "itinerary", "failed"]
    reply: str
    provider: str
    # 第一份展示的方案；一份都没展示时是第一份存下的（板块 5 的接口和测试用）
    version: ItineraryVersion | None = None
    round: PlanningRound | None = None
    versions: list[ItineraryVersion] = field(default_factory=list)


@dataclass
class _Round:
    draft: PlanDraft
    legs: list[ItineraryLeg]
    report: ValidationReport
    model: str | None


@dataclass
class _Plan:
    """一份方案在链路里的状态。"""

    emphasis: Emphasis
    candidates: Candidates
    trip: Frame
    walk_max: int | None
    prompt: str = ""
    first: _Round | None = None
    final: _Round | None = None
    removed: str | None = None


class PlanningPipeline:
    def __init__(
        self,
        *,
        gateway: LLMGateway,
        pois: PoiRepository,
        routes: RouteService,
        itineraries: ItineraryRepository,
        conversations: ConversationRepository,
        rounds: PlanningRoundRepository,
        today: Callable[[], date],
        emphases: Sequence[str] = DEFAULT_EMPHASES,
    ) -> None:
        self.gateway = gateway
        self.pois = pois
        self.routes = routes
        self.itineraries = itineraries
        self.conversations = conversations
        self.rounds = rounds
        self.today = today
        self.emphases = [EMPHASES[e] for e in emphases]

    async def handle(
        self,
        conversation_id: str,
        message: str,
        *,
        provider: str | None,
        on_stage: OnStage | None = None,
    ) -> PlanOutcome:
        """处理一条用户消息。用户消息由调用方先存好。三份都调用模型出错时抛 LLMError，由调用方转成错误回复。"""

        async def stage(name: Stage) -> None:
            if on_stage is not None:
                result = on_stage(name)
                if result is not None:
                    await result

        conv = self.conversations.get(conversation_id)
        if conv is None:
            raise KeyError(conversation_id)
        today = self.today()
        labels = {p.id: p.label for p in self.gateway.providers()}

        # ① 抽偏好
        await stage("understanding")
        extracted = await self.gateway.complete_json(
            task="extract_preferences",
            system_prompt=prompts.EXTRACT_SYSTEM,
            user_prompt=prompts.extract_user_prompt(message, conv.preferences, today),
            schema=TravelerPreferences,
            provider=provider,
        )
        provider_name = extracted.provider
        prefs = merge(conv.preferences, extracted.parsed)  # type: ignore[arg-type]
        self.conversations.save_preferences(conversation_id, prefs)

        # ② 缺关键信息就反问
        asked = {a for m in self.conversations.messages(conversation_id) for a in m.asked}
        question = question_for(prefs, asked, today)
        if question is not None:
            self.conversations.add_message(
                conversation_id, "assistant", question.text, kind="question", asked=question.asked, provider=provider_name
            )
            return PlanOutcome(kind="question", reply=question.text, provider=provider_name)
        if prefs.startDate is None and not prefs.dateUndecided:
            # 问过一次日期，用户还是没说：当作没定
            prefs = prefs.model_copy(update={"dateUndecided": True})
            self.conversations.save_preferences(conversation_id, prefs)

        # ③ 筛候选：三份共用的（去掉暂停开放和用户不去的），再按侧重各自调整
        await stage("selecting")
        trip = frame_for(prefs)
        library = self.pois.list_pois()
        base = select_candidates(library, prefs)
        defaults = list(trip.defaults_used)
        if base.not_in_library:
            defaults.append(f"你提到的{'、'.join(base.not_in_library)}不在景点库里，没有安排")
        if base.closed_requested:
            defaults.append(f"你提到的{'、'.join(base.closed_requested)}现在暂停开放，没有安排")

        previous_rounds = self.rounds.list_rounds(conversation_id)
        previous = previous_rounds[-1] if previous_rounds else None
        plans = [
            _Plan(
                emphasis=e,
                candidates=candidates_for(e, base, library),
                trip=Frame(
                    frame=emphasis_frame(e, trip.frame),
                    transport=trip.transport,
                    defaults_used=_plan_defaults(e, emphasis_frame(e, trip.frame), trip.frame, prefs, defaults),
                ),
                walk_max=walk_limit(e),
            )
            for e in self.emphases
        ]

        # ④ 三份同时生成
        await stage("generating")
        for plan in plans:
            plan.prompt = prompts.generate_user_prompt(
                message=message,
                prefs=prefs,
                frame=plan.trip.frame,
                transport_label=TRANSPORT_LABELS[trip.transport],
                candidates=candidate_brief(plan.candidates, prefs),
                distances=distance_table(plan.candidates),
                previous=self._previous_draft(previous, plan.emphasis.id),
                emphasis=plan.emphasis.prompt,
            )
        generated = await asyncio.gather(
            *(
                self.gateway.complete_json(
                    task="generate_itinerary",
                    system_prompt=prompts.GENERATE_SYSTEM,
                    user_prompt=plan.prompt,
                    schema=PlanDraft,
                    provider=provider_name,
                    # 排行程是慢请求：超时直接报错，不重试（2026-11-15 Cecilia 定的）
                    retry_on_timeout=False,
                )
                for plan in plans
            ),
            return_exceptions=True,
        )
        errors = [g for g in generated if isinstance(g, BaseException)]
        for g in errors:
            if not isinstance(g, LLMError):
                raise g
        if len(errors) == len(plans):
            raise errors[0]
        drafts: dict[int, tuple[PlanDraft, str | None]] = {}
        for i, (plan, g) in enumerate(zip(plans, generated)):
            if isinstance(g, LLMError):
                plan.removed = f"模型没排出来：{g.message}"
            else:
                drafts[i] = (g.parsed, g.model)  # type: ignore[union-attr]

        # ⑤ ⑥ 查交通、校验
        await self._check_all(plans, drafts, today, stage)
        for plan in plans:
            plan.final = plan.first

        # ⑦ 几乎一样的去掉，不再花修正
        self._remove_duplicates(plans)

        # ⑧ 有错误的修正一次
        to_repair = [p for p in plans if p.removed is None and p.first is not None and p.first.report.status == "failed"]
        if to_repair:
            await stage("repairing")
            repaired = await asyncio.gather(
                *(
                    self.gateway.complete_json(
                        task="repair_itinerary",
                        system_prompt=prompts.REPAIR_SYSTEM,
                        user_prompt=prompts.repair_user_prompt(
                            generate_prompt=p.prompt,
                            draft=p.first.draft,  # type: ignore[union-attr]
                            errors=[i.message for i in p.first.report.errors],  # type: ignore[union-attr]
                            legs=_leg_lines(p.first.legs, p.candidates),  # type: ignore[union-attr]
                        ),
                        schema=PlanDraft,
                        provider=provider_name,
                        retry_on_timeout=False,
                    )
                    for p in to_repair
                ),
                return_exceptions=True,
            )
            fixed: dict[int, tuple[PlanDraft, str | None]] = {}
            for p, r in zip(to_repair, repaired):
                if isinstance(r, BaseException):
                    if not isinstance(r, LLMError):
                        raise r
                    # 修正没回来：保留第一轮的结果，下面按"没通过校验"处理
                    p.removed = f"修正时模型出错：{r.message}"
                else:
                    fixed[plans.index(p)] = (r.parsed, r.model)  # type: ignore[union-attr]
            if fixed:
                await self._check_all(plans, fixed, today, stage, into="final")
                self._remove_duplicates(plans)

        for p in plans:
            if p.removed is None and p.final is not None and p.final.report.status == "failed":
                tried = "（修正过一次）" if p.final is not p.first else ""
                p.removed = f"没通过校验：还有 {len(p.final.report.errors)} 处问题{tried}"

        # ⑨ 保存：每份一个版本，记下这一轮
        await stage("saving")
        round_plans: list[RoundPlan] = []
        versions: list[ItineraryVersion] = []
        shown: list[ItineraryVersion] = []
        for p in plans:
            if p.final is None:
                round_plans.append(
                    RoundPlan(emphasis=p.emphasis.id, label=p.emphasis.label, itineraryId=None, versionId=None, shown=False,
                              removedReason=p.removed)
                )
                continue
            data = self._version_data(p, prefs, provider_name, labels, today)
            itinerary_id = self._itinerary_for(previous, p.emphasis.id, conversation_id)
            version = self.itineraries.add_version(itinerary_id, data)
            versions.append(version)
            if p.removed is None:
                shown.append(version)
            round_plans.append(
                RoundPlan(emphasis=p.emphasis.id, label=p.emphasis.label, itineraryId=itinerary_id, versionId=version.id,
                          shown=p.removed is None, removedReason=p.removed)
            )
        saved_round = self.rounds.add_round(
            PlanningRoundData(
                conversationId=conversation_id,
                roundNumber=(previous.roundNumber + 1) if previous else 1,
                provider=provider_name,
                providerLabel=labels.get(provider_name, provider_name),
                plans=round_plans,
                defaultsUsed=defaults,
            )
        )
        first = shown[0] if shown else (versions[0] if versions else None)
        if first is not None and conv.itineraryId is None:
            self.conversations.set_itinerary(conversation_id, first.itineraryId)

        kind: Literal["itinerary", "failed"] = "itinerary" if shown else "failed"
        reply = _reply_text(round_plans, shown)
        self.conversations.add_message(
            conversation_id,
            "assistant",
            reply,
            kind=kind,
            provider=provider_name,
            itinerary_version_id=first.id if first else None,
            planning_round_id=saved_round.id,
        )
        return PlanOutcome(kind=kind, reply=reply, provider=provider_name, version=first, round=saved_round, versions=versions)

    # ---------- 小步骤 ----------

    def _previous_draft(self, previous: PlanningRound | None, emphasis: str) -> PlanDraft | None:
        if previous is None:
            return None
        plan = next((p for p in previous.plans if p.emphasis == emphasis and p.versionId), None)
        if plan is None or plan.versionId is None:
            return None
        version = self.itineraries.get_version(plan.versionId)
        return version.draft if version else None

    def _itinerary_for(self, previous: PlanningRound | None, emphasis: str, conversation_id: str) -> str:
        """同一侧重沿用上一轮的行程（新的一轮是它的下一个版本）；没有就新建。"""
        if previous is not None:
            plan = next((p for p in previous.plans if p.emphasis == emphasis and p.itineraryId), None)
            if plan is not None and plan.itineraryId is not None:
                return plan.itineraryId
        return self.itineraries.create_itinerary(conversation_id)

    async def _check_all(
        self,
        plans: list[_Plan],
        drafts: dict[int, tuple[PlanDraft, str | None]],
        today: date,
        stage: Callable[[Stage], Awaitable[None]],
        into: Literal["first", "final"] = "first",
    ) -> None:
        # 交通一份一份查：高德请求本来就排队一个一个发，三份用到的路线大多相同，缓存里有的不再查
        await stage("routing")
        legs: dict[int, list[ItineraryLeg]] = {}
        for i, (draft, _) in drafts.items():
            legs[i] = await self._route(plans[i], draft)
        await stage("validating")
        for i, (draft, model) in drafts.items():
            plan = plans[i]
            leg_map = {(leg.fromPoiId, leg.toPoiId): leg.route for leg in legs[i]}
            report = validate_itinerary(draft, pois=plan.candidates.pois, legs=leg_map, frame=plan.trip.frame, today=today)
            extra = check_emphasis(plan.emphasis, draft, candidates=plan.candidates, legs=leg_map, frame=plan.trip.frame)
            result = _Round(draft=draft, legs=legs[i], report=merge_issues(report, extra), model=model)
            setattr(plan, into, result)

    async def _route(self, plan: _Plan, draft: PlanDraft) -> list[ItineraryLeg]:
        out: list[ItineraryLeg] = []
        pois = plan.candidates.pois
        for day in draft.days:
            for prev, nxt in zip(day.stops, day.stops[1:]):
                if prev.poiId in pois and nxt.poiId in pois and prev.poiId != nxt.poiId:
                    out.append(
                        await choose_leg(self.routes, prev.poiId, nxt.poiId, plan.trip.transport, walk_max=plan.walk_max)
                    )
        return out

    @staticmethod
    def _remove_duplicates(plans: list[_Plan]) -> None:
        """按"经典 → 轻松 → 深度"的顺序，和前面留下的某一份几乎一样的去掉。"""
        kept: list[_Plan] = []
        for p in plans:
            if p.removed is not None or p.final is None:
                continue
            for k in kept:
                reason = near_duplicate(k.final.draft, p.final.draft)  # type: ignore[union-attr]
                if reason is not None:
                    p.removed = f"和「{k.emphasis.label}」几乎一样：{reason}"
                    break
            else:
                kept.append(p)

    def _version_data(
        self,
        p: _Plan,
        prefs: TravelerPreferences,
        provider_name: str,
        labels: dict[str, str],
        today: date,
    ) -> ItineraryVersionData:
        final, first = p.final, p.first
        assert final is not None and first is not None
        data = ItineraryVersionData(
            title=final.draft.title or f"武汉 {p.trip.frame.days} 日 · {p.emphasis.label}",
            frame=p.trip.frame,
            preferences=prefs,
            defaultsUsed=p.trip.defaults_used,
            days=_build_days(final, p.candidates, p.trip.frame, today),
            validation=final.report,
            planner=PlannerInfo(
                provider=provider_name,
                providerLabel=labels.get(provider_name, provider_name),
                model=final.model,
                rounds=1 if final is first else 2,
                firstRoundStatus=first.report.status,
                firstRoundErrors=len(first.report.errors),
            ),
            draft=final.draft,
            dataAsOf=today,
            emphasis=p.emphasis.id,
        )
        data.metrics = plan_metrics(data)
        return data


def _plan_defaults(
    emphasis: Emphasis, frame: TripFrame, shared: TripFrame, prefs: TravelerPreferences, defaults: list[str]
) -> list[str]:
    """一份方案的"按默认补的设置"。侧重改了节奏（轻松少走路按轻松排）时，不能再写三份共用的"节奏：适中（按默认）"。"""
    if frame.pace == shared.pace:
        return list(defaults)
    said = f"；你说的是{PACE_LABELS[prefs.pace]}" if prefs.pace is not None else ""
    note = f"节奏：{PACE_LABELS[frame.pace]}（这份是「{emphasis.label}」，按{PACE_LABELS[frame.pace]}排{said}）"
    return [d for d in defaults if not d.startswith("节奏：")] + [note]


# ---------- 存进版本的快照 ----------


def _fact_out(poi: PoiFile, fact: Fact[Any] | None, today: date) -> dict[str, Any]:
    sources = {s.id: SourceOut(**s.model_dump()) for s in poi.sources}
    if fact is None:
        return {"value": None, "verification": "todo", "status": "missing", "source": None,
                "lastCheckedAt": None, "expiresAt": None, "todo": None, "note": None}
    return {
        "value": fact.value,
        "verification": fact.verification,
        "status": fact_status(fact, today),
        "source": sources.get(fact.sourceId) if fact.sourceId else None,
        "lastCheckedAt": fact.lastCheckedAt,
        "expiresAt": fact.expiresAt,
        "todo": fact.todo,
        "note": fact.note,
    }


def _build_days(final: _Round, candidates: Candidates, frame: TripFrame, today: date) -> list[ItineraryDay]:
    legs = {(leg.fromPoiId, leg.toPoiId): leg for leg in final.legs}
    days: list[ItineraryDay] = []
    for day in final.draft.days:
        stops: list[ItineraryStop] = []
        for s in day.stops:
            poi = candidates.pois.get(s.poiId)
            if poi is None or poi.location is None or poi.location.value is None:
                continue  # 不存在的景点只留在 draft 里，校验结果里有错误
            facts = StopFacts.model_validate(
                {
                    name: _fact_out(poi, getattr(poi, name), today)
                    for name in ("openingHours", "reservation", "ticket", "payment", "recommendedDurationMinutes")
                }
            )
            stops.append(
                ItineraryStop(
                    poiId=poi.id,
                    name=poi.name,
                    district=poi.district,
                    category=poi.category,
                    location=poi.location.value,
                    arrive=s.arrive,
                    leave=s.leave,
                    reason=s.reason,
                    facts=facts,
                )
            )
        day_legs = [legs[(a.poiId, b.poiId)] for a, b in zip(stops, stops[1:]) if (a.poiId, b.poiId) in legs]
        days.append(
            ItineraryDay(
                dayNumber=day.dayNumber,
                date=day_date(frame, day.dayNumber),
                theme=day.theme,
                stops=stops,
                legs=day_legs,
            )
        )
    return days


def _leg_lines(legs: list[ItineraryLeg], candidates: Candidates) -> list[str]:
    out = []
    for leg in legs:
        a = candidates.pois[leg.fromPoiId].name
        b = candidates.pois[leg.toPoiId].name
        r = leg.route
        if r.status == "ok" and r.durationMinutes is not None:
            out.append(f"{a}（{leg.fromPoiId}）到{b}（{leg.toPoiId}）：{MODE_LABELS[r.mode]} {r.durationMinutes} 分钟")
        else:
            out.append(f"{a}（{leg.fromPoiId}）到{b}（{leg.toPoiId}）：没查到")
    return out


def _reply_text(plans: list[RoundPlan], shown: list[ItineraryVersion]) -> str:
    total = len(plans)
    hidden = [p for p in plans if not p.shown]
    why = "".join(f"「{p.label}」没有展示：{p.removedReason}。" for p in hidden)
    if not shown:
        return f"这次排的 {total} 份方案都不能展示。{why}可以换个说法或调整要求再试。"
    names = "、".join(f"「{p.label}」" for p in plans if p.shown)
    head = f"排了 {total} 份方案，展示 {len(shown)} 份：{names}。" if total > 1 else "排好了。"
    repaired = sum(1 for v in shown if v.planner.rounds == 2)
    fixed = f"其中 {repaired} 份第一版有错误，交给模型修正过一次。" if repaired else ""
    warnings = [len(v.validation.warnings) for v in shown]
    if any(warnings):
        checked = f"校验没有发现错误，警告分别有 {'、'.join(str(w) for w in warnings)} 条，主要是有些资料还没核实，详情在行程卡上。"
    else:
        checked = "校验通过。"
    return head + fixed + checked + why
