"""双模型并排对比（板块 6）：同一个请求交给两个模型并排运行，结果存进 SQLite。

    请求 → 偏好（页面：默认模型抽一次，两边共用；批量评测：手写好的）
         → 千问 plan_single ┐ 同时跑，同一条链路、同一份偏好、同一份候选、同一种侧重
         → 豆包 plan_single ┘ （各自生成 → 查交通 → 校验 → 有错误修正一次 → 存版本）
         → 每边的数字、两份的差异、对比表（model_compare.py，全部由程序算）→ 存一次对比

两边用同一个 PlanningPipeline：路线服务和高德的请求队列是同一个，查交通照样一个一个发，缓存里有的不再查。
每边的模型调用用 collect_calls 分开收集（失败的也算），抽偏好那次单独记，不算在任何一边。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from time import perf_counter

from app.repositories.model_comparison_repository import ModelComparisonRepository
from app.schemas.comparison import ModelComparison, ModelComparisonData, SideResult
from app.schemas.itinerary import ItineraryVersion
from app.schemas.planning import TravelerPreferences
from app.services.llm.collect import collect_calls
from app.services.planning import prompts
from app.services.planning.emphasis import EMPHASES
from app.services.planning.model_compare import call_stats, comparison_table, plan_diff, side_result
from app.services.planning.pipeline import PlanningPipeline

# 左边、右边。顺序固定，页面和汇总都按这个顺序
DEFAULT_PROVIDERS: tuple[str, str] = ("qwen", "doubao")

# 进度：每边走到哪一步（provider → 步骤），以及共用的步骤
OnProgress = Callable[[str | None, str], None]


class NeedsMoreInfo(Exception):
    """请求里缺天数。对比页不反问，直接让用户把天数写进请求。"""


class ModelComparer:
    def __init__(self, pipeline: PlanningPipeline, comparisons: ModelComparisonRepository) -> None:
        self.pipeline = pipeline
        self.comparisons = comparisons

    async def compare(
        self,
        request: str,
        *,
        emphasis: str = "classic",
        prefs: TravelerPreferences | None = None,
        providers: Sequence[str] = DEFAULT_PROVIDERS,
        extractor: str | None = None,
        eval_request_id: str | None = None,
        on_progress: OnProgress | None = None,
    ) -> ModelComparison:
        """prefs 不给就用 extractor（不填用默认模型）从请求里抽一次。抽偏好出错时抛 LLMError。"""

        def progress(provider: str | None, stage: str) -> None:
            if on_progress is not None:
                on_progress(provider, stage)

        if emphasis not in EMPHASES:
            raise ValueError(f"没有这种侧重：{emphasis}")
        gateway = self.pipeline.gateway
        labels = {p.id: p.label for p in gateway.providers()}

        source: str = "given"
        extractor_calls = None
        used_extractor: str | None = None
        if prefs is None:
            progress(None, "understanding")
            source = "extracted"
            with collect_calls() as calls:
                result = await gateway.complete_json(
                    task="extract_preferences",
                    system_prompt=prompts.EXTRACT_SYSTEM,
                    user_prompt=prompts.extract_user_prompt(request, TravelerPreferences(), self.pipeline.today()),
                    schema=TravelerPreferences,
                    provider=extractor,
                )
            prefs = result.parsed  # type: ignore[assignment]
            used_extractor = result.provider
            extractor_calls = call_stats(calls)
        assert prefs is not None
        if prefs.days is None:
            raise NeedsMoreInfo("请在请求里写明玩几天，例如「武汉两天」。对比页不反问，偏好要一次说清楚。")
        if prefs.startDate is None and not prefs.dateUndecided:
            prefs = prefs.model_copy(update={"dateUndecided": True})

        library = self.pipeline.pois.list_pois()
        library_ids = {p.id for p in library}
        names = {p.id: p.name for p in library}

        # 给模型看的真实交通表先算一份，两边共用（板块 6B）：两边同时跑，各算各的话，
        # 后开始的一边可能读到先开始的一边刚查进缓存的路线，提示词就不一样了
        transit = self.pipeline.transit_for(prefs, emphasis)

        async def one_side(provider: str) -> tuple[SideResult, ItineraryVersion | None, list[str]]:
            started = perf_counter()
            with collect_calls() as calls:
                out = await self.pipeline.plan_single(
                    message=request, prefs=prefs, emphasis=emphasis, provider=provider,
                    on_stage=lambda s: progress(provider, s), transit=transit,
                )
            wall = round((perf_counter() - started) * 1000)
            side = side_result(
                provider=provider,
                provider_label=labels.get(provider, provider),
                calls=calls,
                wall_ms=wall,
                library_ids=library_ids,
                version=out.version,
                version_id=out.version.id if out.version else None,
                error=out.error,
            )
            progress(provider, "done")
            return side, out.version, out.defaults

        results = await asyncio.gather(*(one_side(p) for p in providers))
        sides = [r[0] for r in results]
        versions = [r[1] for r in results]
        defaults = next((r[2] for r in results if r[2]), [])

        progress(None, "saving")
        both = [v for v in versions if v is not None]
        data = ModelComparisonData(
            request=request,
            preferences=prefs,
            preferencesSource=source,  # type: ignore[arg-type]
            extractor=used_extractor,
            extractorCalls=extractor_calls,
            emphasis=emphasis,
            emphasisLabel=EMPHASES[emphasis].label,
            defaultsUsed=defaults,
            sides=sides,
            diff=plan_diff(both[0], both[1]) if len(both) == 2 and len(versions) == 2 else None,
            table=comparison_table(sides, versions, names),
            evalRequestId=eval_request_id,
        )
        return self.comparisons.add(data)
