/**
 * 模型接口返回的数据结构，和后端 apps/api/app/schemas/llm.py 对应。
 * GET /api/llm/providers → LlmProviders；POST /api/llm/ping → LlmPing。
 * 字段说明见 docs/architecture/api-contracts.md 的"模型"一节。
 */

/** 现在有的模型。后端加了新的模型，这里也要加 */
export type LlmProviderId = "qwen" | "doubao";

export interface LlmProvider {
  id: LlmProviderId;
  label: string;
  /** 后端的 .env 里这个模型的 key 和模型名都填了。前端拿不到 key */
  configured: boolean;
  isDefault: boolean;
}

export interface LlmProviders {
  /** .env 里 LLM_PROVIDER 指的模型；填的不是可用的模型时是 null */
  defaultProvider: LlmProviderId | null;
  providers: LlmProvider[];
}

/** 临时的"试一句"的结果（板块 5 接上对话后去掉） */
export interface LlmPing {
  provider: LlmProviderId;
  label: string;
  /** 对方返回的真实模型名 */
  model: string;
  reply: string;
  /** 从开始到结束的总时间，含重试之间的等待 */
  latencyMs: number;
  /** 一共向模型发了几次请求 */
  attempts: number;
  /** 有没有因为超时、限流、对方出错而重试 */
  retried: boolean;
  /** 有没有因为输出不合格让模型重答 */
  repaired: boolean;
}

/** 经过 LLMGateway 的接口出错时，回应里的 detail */
export interface LlmError {
  code: string;
  message: string;
  retryable: boolean;
  provider: string | null;
}
