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
