# ADR 0002: LLM Provider Gateway for Doubao and Qwen

日期: 2026-07-05

## 状态

Accepted.

## 背景

项目需要支持中国大模型服务，用户明确要求豆包和 Qwen 都可以切换。旅行规划任务需要结构化输出、工具调用、错误恢复和可观测性。如果业务代码直接依赖某一家模型 SDK，会导致后续切换、回退和质量对比困难。

## 决策

后端新增 `LLMGateway` 和 provider 适配层:

- `QwenProvider`
- `DoubaoProvider`
- `MockLLMProvider`

业务层只依赖统一接口:

- `complete_json`
- `complete_with_tools`

Provider 选择通过环境变量控制:

- `LLM_PROVIDER`
- `LLM_FALLBACK_PROVIDER`
- `LLM_PROVIDER_MODE`

MVP 默认使用 mock provider。真实环境推荐 `qwen` 为主 provider，`doubao` 为 fallback provider，但可按成本、质量、延迟和可用性调整。

## 理由

- 豆包和 Qwen 都有 OpenAI 兼容 API 形态，适合以统一 Chat Completions 风格封装。
- 不同 provider 对结构化输出、工具调用、错误码、模型名和限流的细节不同，需要隔离。
- 旅行规划的正确性不能只依赖模型，需要统一的 schema 校验和业务校验。
- fallback 和 shadow 模式能帮助后续做稳定性和质量对比。

## 影响

正向:

- AI provider 可切换。
- 方便做 A/B 测试和质量评估。
- 失败时可以自动降级。
- 避免供应商锁定。

代价:

- 后端多一层抽象和测试成本。
- 不同 provider 的工具调用细节需要持续维护。
- 需要统一 token usage、错误码和响应 trace。

## 后续任务

- 实现 `LLMGateway`。
- 为豆包和 Qwen 各写 mock HTTP 单元测试。
- 在 planning job trace 中记录 provider、model、latency 和 schema validation result。
- 有真实 key 后增加 smoke test。

## 2026-11-15 更新（板块 4）

上面的决策不变：业务代码只认 `LLMGateway`，千问和豆包各有一个 provider。实现时定下来的几点：

- **分工**：provider 只发一次请求、翻译错误；重试、限流等待、输出检查、让模型重答、记录都在网关里。这样网关的逻辑可以用假 provider 测，不用联网。
- **切换**：`.env` 的 `LLM_PROVIDER` 是默认模型；每次请求可以用 `provider` 参数另外指定；界面上的模型选择用的就是这个参数。
- **自动换备用模型默认关**（Cecilia 定的）。悄悄换模型会让"这次用了哪个模型"说不清，也会搅乱板块 6 的对比。配置项保留。
- **mock provider 移出应用代码**。默认模型从 `mock` 改成 `qwen`；测试用 `apps/api/tests/llm_fakes.py` 里的假 provider。
- **接口从两个减到一个**：只有 `complete_json`。`complete_with_tools` 和 shadow 模式没有做，要不要做留到板块 5、6。
- **每次调用记一行到 SQLite 的 `llm_calls`**，不存提示词和回答（Cecilia 定的）。
- **不引入两家的 SDK**，继续用 httpx 直接调 OpenAI 兼容接口。
- **豆包的深度思考保持模型默认**（Cecilia 定的，2026-11-15），可以用 `DOUBAO_THINKING` 改。

"后续任务"里的四条都已完成。现在的样子见 `docs/architecture/llm-provider-gateway.md`。
