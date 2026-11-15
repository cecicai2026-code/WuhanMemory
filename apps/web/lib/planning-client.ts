/**
 * 浏览器里调用对话和规划接口（板块 5）。字段说明见 docs/architecture/api-contracts.md 的"对话和规划"一节。
 */
import type {
  CompareJob,
  Conversation,
  ItineraryVersion,
  ModelComparison,
  ModelComparisonSummary,
  PlanningJob,
  PlanningRound,
  SendMessageResponse,
} from "@wuhanmemory/shared";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** 后端连不上，或返回了错误 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: init?.body ? { "content-type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(`连不上后端 ${API_BASE}。先启动后端：corepack pnpm dev:api`, null);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof (detail as { message?: unknown }).message === "string"
          ? (detail as { message: string }).message
          : `后端返回 ${res.status}`;
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}

export function createConversation(): Promise<{ conversationId: string }> {
  return call("/api/conversations", { method: "POST", body: JSON.stringify({ city: "武汉" }) });
}

export function getConversation(id: string): Promise<Conversation> {
  return call(`/api/conversations/${encodeURIComponent(id)}`);
}

export function sendMessage(conversationId: string, content: string, provider: string | null): Promise<SendMessageResponse> {
  return call(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, provider }),
  });
}

export function getJob(jobId: string): Promise<PlanningJob> {
  return call(`/api/planning-jobs/${encodeURIComponent(jobId)}`);
}

export function getVersion(versionId: string): Promise<ItineraryVersion> {
  return call(`/api/itinerary-versions/${encodeURIComponent(versionId)}`);
}

export function getRound(roundId: string): Promise<PlanningRound> {
  return call(`/api/planning-rounds/${encodeURIComponent(roundId)}`);
}

// ---------- 双模型对比（板块 6），字段说明见 api-contracts.md 的"双模型对比"一节 ----------

export function startComparison(request: string, emphasis: string): Promise<{ jobId: string; status: CompareJob["status"] }> {
  return call("/api/comparisons", { method: "POST", body: JSON.stringify({ request, emphasis }) });
}

export function getCompareJob(jobId: string): Promise<CompareJob> {
  return call(`/api/comparison-jobs/${encodeURIComponent(jobId)}`);
}

export function getComparison(id: string): Promise<ModelComparison> {
  return call(`/api/comparisons/${encodeURIComponent(id)}`);
}

export function listComparisons(): Promise<ModelComparisonSummary[]> {
  return call("/api/comparisons");
}
