"""把一段代码里发生的模型调用记录收集起来（板块 6：双模型对比要分清每次调用算哪一边）。

    with collect_calls() as calls:
        await pipeline.plan_single(...)
    # calls 里是这段代码（包括它里面 asyncio.gather 出去的子任务）的每一次网关调用，成功失败都有

用 contextvars 实现：两个模型在两个任务里同时跑，各自的 collect_calls() 互不干扰，
不用按时间或模型名去 llm_calls 表里猜哪条是谁的。网关照常把记录写进 llm_calls，这里只是多留一份。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.services.llm.base import LLMCallRecord

_current: ContextVar[list[LLMCallRecord] | None] = ContextVar("llm_call_collector", default=None)


def note_call(record: LLMCallRecord) -> None:
    """网关每次调用结束时调用。外面没有 collect_calls() 时什么都不做。"""
    calls = _current.get()
    if calls is not None:
        calls.append(record)


@contextmanager
def collect_calls() -> Iterator[list[LLMCallRecord]]:
    calls: list[LLMCallRecord] = []
    token = _current.set(calls)
    try:
        yield calls
    finally:
        _current.reset(token)
