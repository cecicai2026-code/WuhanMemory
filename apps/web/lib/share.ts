/**
 * 分享页的数据入口（板块 7）：GET /api/share/{slug}。只在服务器端调用（分享页是服务器组件）。
 */
import type { ItineraryVersion, ShareLink, SharePage } from "@wuhanmemory/shared";
import { ApiUnavailableError } from "./places";

const API_BASE = (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type ShareResult = { kind: "ok"; page: SharePage } | { kind: "revoked" } | { kind: "missing" };

export async function getSharePage(slug: string): Promise<ShareResult> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/share/${encodeURIComponent(slug)}`, { cache: "no-store" });
  } catch {
    throw new ApiUnavailableError(`连不上后端 ${API_BASE}`);
  }
  if (res.status === 404) return { kind: "missing" };
  if (res.status === 410) return { kind: "revoked" };
  if (!res.ok) throw new ApiUnavailableError(`后端返回 ${res.status}`);
  return { kind: "ok", page: (await res.json()) as SharePage };
}

/** 一个版本，服务器端取（/trips/[versionId] 用）。没有这个版本时返回 null。 */
export async function getVersionOnServer(versionId: string): Promise<ItineraryVersion | null> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/itinerary-versions/${encodeURIComponent(versionId)}`, { cache: "no-store" });
  } catch {
    throw new ApiUnavailableError(`连不上后端 ${API_BASE}`);
  }
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiUnavailableError(`后端返回 ${res.status}`);
  return (await res.json()) as ItineraryVersion;
}

/** 这个版本现在没撤回的分享链接，服务器端取；没有时返回 null。 */
export async function getActiveShareOnServer(versionId: string): Promise<ShareLink | null> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/itinerary-versions/${encodeURIComponent(versionId)}/share`, { cache: "no-store" });
  } catch {
    throw new ApiUnavailableError(`连不上后端 ${API_BASE}`);
  }
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiUnavailableError(`后端返回 ${res.status}`);
  return (await res.json()) as ShareLink;
}
