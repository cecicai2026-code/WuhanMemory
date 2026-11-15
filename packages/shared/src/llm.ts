/**
 * 模型接口返回的数据结构，和后端 apps/api/app/schemas/llm.py 对应。
 * GET /api/llm/providers → LlmProviders。
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

/** 模型出错时的说明（规划任务的 error） */
export interface LlmError {
  code: string;
  message: string;
  retryable: boolean;
  provider: string | null;
}
