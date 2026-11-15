"""冒烟脚本的测试。脚本本身是给真实接口用的；这里用假 provider 只测它打印什么、返回什么。"""

from __future__ import annotations

from app.services.llm.errors import LLMAuthError
from app.services.llm.gateway import LLMGateway
from app.tools.llm_smoke import USER_PROMPT, run
from tests.llm_fakes import FakeProvider, Records, Sleeps

GOOD = '{"province": "湖北省"}'


def make(*providers: FakeProvider) -> tuple[LLMGateway, Records]:
    records = Records()
    gateway = LLMGateway(
        providers={provider.name: provider for provider in providers},
        default_provider=providers[0].name,
        recorder=records,
        sleep=Sleeps(),
    )
    return gateway, records


async def test_both_models_get_the_same_request_and_pass() -> None:
    a, b = FakeProvider("a", script=[GOOD]), FakeProvider("b", script=[GOOD], model="other-model")
    gateway, records = make(a, b)
    lines: list[str] = []

    failed = await run(gateway, lines.append)

    assert failed == 0
    assert a.calls[0][1].content == b.calls[0][1].content == USER_PROMPT
    text = "\n".join(lines)
    assert text.count("结果：成功") == 2
    assert "模型名：fake-model-1" in text and "模型名：other-model" in text
    assert "耗时：" in text and "湖北省" in text
    assert "汇总：2 / 2 个模型通过" in text
    assert [(record.task, record.provider) for record in records.items] == [("smoke", "a"), ("smoke", "b")]


async def test_one_failure_does_not_stop_the_other_model() -> None:
    a = FakeProvider("a", script=[LLMAuthError("假模型 a 的 key 无效（HTTP 401）")])
    b = FakeProvider("b", script=[GOOD])
    gateway, _ = make(a, b)
    lines: list[str] = []

    failed = await run(gateway, lines.append)

    assert failed == 1
    text = "\n".join(lines)
    assert "结果：失败（invalid_key）" in text and "key 无效（HTTP 401）" in text
    assert "结果：成功" in text
    assert "汇总：1 / 2 个模型通过" in text


async def test_unconfigured_model_is_skipped_and_counts_as_not_passed() -> None:
    a, b = FakeProvider("a", script=[GOOD]), FakeProvider("b", configured=False)
    gateway, _ = make(a, b)
    lines: list[str] = []

    failed = await run(gateway, lines.append)

    assert failed == 1
    assert b.calls == []
    assert "没有配置" in "\n".join(lines)
