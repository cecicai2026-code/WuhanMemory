"""规划链路：一条用户消息进来，到反问、合格的行程或明确的失败说明出去。

    ① 抽偏好（模型） → ② 缺天数/日期就反问（程序） → ③ 筛候选（程序）
    → ④ 生成行程（模型） → ⑤ 查相邻两站的真实交通（程序，高德） → ⑥ validate_itinerary（程序）
    → ⑦ 有错误：把具体错误交给模型修正一次，再做 ⑤ ⑥ → ⑧ 保存版本（程序）

模型只做两件事：听懂用户的话，在候选里挑景点排时间。景点资料、交通时间、预约和支付提示都由程序从景点库和高德取；
行程能不能给用户看，由 validate_itinerary 决定，不由模型决定。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.poi_repository import PoiRepository
from app.schemas.itinerary import (
    ItineraryDay,
    ItineraryLeg,
    ItineraryStop,
    ItineraryVersion,
    ItineraryVersionData,
    PlannerInfo,
    StopFacts,
)
from app.schemas.planning import PlanDraft, TravelerPreferences, TripFrame, ValidationReport
from app.schemas.poi import Fact, PoiFile
from app.schemas.poi_api import SourceOut
from app.services.llm.gateway import LLMGateway
from app.services.planning import prompts
from app.services.planning.candidates import Candidates, candidate_brief, distance_table, select_candidates
from app.services.planning.preferences import TRANSPORT_LABELS, Frame, frame_for, merge, question_for
from app.services.planning.transport import MODE_LABELS, choose_leg
from app.services.planning.validate import day_date, validate_itinerary
from app.services.poi_view import fact_status
from app.services.routing.service import RouteService

# 界面上显示的规划步骤。顺序就是链路的顺序；repairing 只在第一轮有错误时出现。
Stage = Literal["understanding", "selecting", "generating", "routing", "validating", "repairing", "saving"]
STAGE_LABELS: dict[str, str] = {
    "understanding": "理解需求",
    "selecting": "从景点库挑候选",
    "generating": "模型排行程",
    "routing": "查真实交通时间",
    "validating": "校验",
    "repairing": "把错误交给模型修正",
    "saving": "保存",
}

OnStage = Callable[[str], Awaitable[None] | None]


@dataclass
class PlanOutcome:
    kind: Literal["question", "itinerary", "failed"]
    reply: str
    provider: str
    version: ItineraryVersion | None = None


@dataclass
class _Round:
    draft: PlanDraft
    legs: list[ItineraryLeg]
    report: ValidationReport
    model: str | None


class PlanningPipeline:
    def __init__(
        self,
        *,
        gateway: LLMGateway,
        pois: PoiRepository,
        routes: RouteService,
        itineraries: ItineraryRepository,
        conversations: ConversationRepository,
        today: Callable[[], date],
    ) -> None:
        self.gateway = gateway
        self.pois = pois
        self.routes = routes
        self.itineraries = itineraries
        self.conversations = conversations
        self.today = today

    async def handle(
        self,
        conversation_id: str,
        message: str,
        *,
        provider: str | None,
        on_stage: OnStage | None = None,
    ) -> PlanOutcome:
        """处理一条用户消息。用户消息由调用方先存好。模型出错时抛 LLMError，由调用方转成错误回复。"""

        async def stage(name: Stage) -> None:
            if on_stage is not None:
                result = on_stage(name)
                if result is not None:
                    await result

        conv = self.conversations.get(conversation_id)
        if conv is None:
            raise KeyError(conversation_id)
        today = self.today()
        provider_name = provider or self.gateway.default_provider
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

        # ③ 筛候选
        await stage("selecting")
        trip = frame_for(prefs)
        candidates = select_candidates(self.pois.list_pois(), prefs)
        defaults = list(trip.defaults_used)
        if candidates.not_in_library:
            defaults.append(f"你提到的{'、'.join(candidates.not_in_library)}不在景点库里，没有安排")

        previous: PlanDraft | None = None
        if conv.itineraryId:
            versions = self.itineraries.list_versions(conv.itineraryId)
            if versions:
                previous = versions[-1].draft

        # ④ 生成
        await stage("generating")
        gen_prompt = prompts.generate_user_prompt(
            message=message,
            prefs=prefs,
            frame=trip.frame,
            transport_label=TRANSPORT_LABELS[trip.transport],
            candidates=candidate_brief(candidates, prefs),
            distances=distance_table(candidates),
            previous=previous,
        )
        generated = await self.gateway.complete_json(
            task="generate_itinerary",
            system_prompt=prompts.GENERATE_SYSTEM,
            user_prompt=gen_prompt,
            schema=PlanDraft,
            provider=provider_name,
            # 排行程是慢请求：超时直接报错，不重试（2026-11-15 Cecilia 定的）
            retry_on_timeout=False,
        )
        first = await self._check(generated.parsed, generated.model, candidates, trip, today, stage)  # type: ignore[arg-type]
        final = first

        # ⑦ 有错误：修正一次
        if first.report.status == "failed":
            await stage("repairing")
            repaired = await self.gateway.complete_json(
                task="repair_itinerary",
                system_prompt=prompts.REPAIR_SYSTEM,
                user_prompt=prompts.repair_user_prompt(
                    generate_prompt=gen_prompt,
                    draft=first.draft,
                    errors=[i.message for i in first.report.errors],
                    legs=_leg_lines(first.legs, candidates),
                ),
                schema=PlanDraft,
                provider=provider_name,
                retry_on_timeout=False,
            )
            final = await self._check(repaired.parsed, repaired.model, candidates, trip, today, stage)  # type: ignore[arg-type]

        # ⑧ 保存
        await stage("saving")
        data = ItineraryVersionData(
            title=final.draft.title or f"武汉 {trip.frame.days} 日",
            frame=trip.frame,
            preferences=prefs,
            defaultsUsed=defaults,
            days=_build_days(final, candidates, trip.frame, today),
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
        )
        itinerary_id = conv.itineraryId
        if itinerary_id is None:
            itinerary_id = self.itineraries.create_itinerary(conversation_id)
            self.conversations.set_itinerary(conversation_id, itinerary_id)
        version = self.itineraries.add_version(itinerary_id, data)

        kind: Literal["itinerary", "failed"] = "failed" if final.report.status == "failed" else "itinerary"
        reply = _reply_text(version)
        self.conversations.add_message(
            conversation_id, "assistant", reply, kind=kind, provider=provider_name, itinerary_version_id=version.id
        )
        return PlanOutcome(kind=kind, reply=reply, provider=provider_name, version=version)

    async def _check(
        self,
        draft: PlanDraft,
        model: str | None,
        candidates: Candidates,
        trip: Frame,
        today: date,
        stage: Callable[[Stage], Awaitable[None]],
    ) -> _Round:
        await stage("routing")
        legs: list[ItineraryLeg] = []
        for day in draft.days:
            for prev, nxt in zip(day.stops, day.stops[1:]):
                if prev.poiId in candidates.pois and nxt.poiId in candidates.pois and prev.poiId != nxt.poiId:
                    legs.append(await choose_leg(self.routes, prev.poiId, nxt.poiId, trip.transport))
        await stage("validating")
        report = validate_itinerary(
            draft,
            pois=candidates.pois,
            legs={(leg.fromPoiId, leg.toPoiId): leg.route for leg in legs},
            frame=trip.frame,
            today=today,
        )
        return _Round(draft=draft, legs=legs, report=report, model=model)


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


def _reply_text(version: ItineraryVersion) -> str:
    report = version.validation
    rounds = "（第一版有错误，交给模型修正过一次）" if version.planner.rounds == 2 else ""
    if report.status == "failed":
        return (
            f"这次没能排出合格的行程{rounds}：还有 {len(report.errors)} 处问题，所以不展示这份行程。"
            "问题列在右边，可以换个说法或调整要求再试。"
        )
    if report.status == "warning":
        return f"排好了{rounds}。校验没有发现错误，但有 {len(report.warnings)} 条警告，主要是有些资料还没核实，详情在行程卡上。"
    return f"排好了{rounds}，校验通过。"
