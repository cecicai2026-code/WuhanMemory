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
  ShareLink,
  TripConversation,
} from "@wuhanmemory/shared";

import { backendDownMessage } from "./backend";
import { getOwnerPasscode } from "./owner-passcode";

/** 浏览器里用相对路径，由网站转给后端（lib/backend.ts） */
export const API_BASE = "";

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
    const headers: Record<string, string> = {};
    if (init?.body) headers["content-type"] = "application/json";
    // 公开模式下，我的行程和分享管理要口令；规划带口令时不限次数（板块 7）
    const passcode = typeof window !== "undefined" ? getOwnerPasscode() : null;
    if (passcode) headers["X-Owner-Passcode"] = passcode;
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init, headers });
  } catch {
    throw new ApiError(backendDownMessage(), null);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    // 后端没开时，网站的转发返回 5xx 而且不是后端的 JSON
    if (!body && res.status >= 500) throw new ApiError(backendDownMessage(), null);
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

// ---------- 分享和我的行程（板块 7），字段说明见 api-contracts.md 的"分享"和"我的行程"两节 ----------

/** 给一个版本生成分享链接；已经有没撤回的链接时给回那一个。没通过校验的版本后端会拒绝（409）。 */
export function publishShare(versionId: string): Promise<ShareLink> {
  return call(`/api/itinerary-versions/${encodeURIComponent(versionId)}/share`, { method: "POST" });
}

/** 这个版本现在没撤回的分享链接；没有时返回 null */
export async function getVersionShare(versionId: string): Promise<ShareLink | null> {
  try {
    return await call<ShareLink>(`/api/itinerary-versions/${encodeURIComponent(versionId)}/share`);
  } catch (err) {
    // 404：还没有链接；401：公开模式下要口令，先当作没有，点"生成"时再要口令
    if (err instanceof ApiError && (err.status === 404 || err.status === 401)) return null;
    throw err;
  }
}

export function revokeShare(slug: string): Promise<ShareLink> {
  return call(`/api/share/${encodeURIComponent(slug)}`, { method: "DELETE" });
}

export function listTrips(): Promise<TripConversation[]> {
  return call("/api/trips");
}

