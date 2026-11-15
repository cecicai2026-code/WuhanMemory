/**
 * 分享链接和我的行程（板块 7）。对应后端 apps/api/app/schemas/share.py、trips.py。
 * 字段说明见 docs/architecture/api-contracts.md 的"分享"和"我的行程"两节。
 */
import type { ItineraryVersion } from "./planning";

export interface ShareLink {
  /** 8 位随机小写字母和数字 */
  slug: string;
  versionId: string;
  createdAt: string;
  /** 撤回的时间；没撤回为 null */
  revokedAt: string | null;
  /** 网站上的路径，例如 /s/k3f9x2qa；完整网址由前端按当前网站拼 */
  path: string;
}

export interface SharePage {
  slug: string;
  createdAt: string;
  /** 分享时绑定的那个版本（不可变快照） */
  version: ItineraryVersion;
}

export interface TripVersionSummary {
  id: string;
  versionNumber: number;
  createdAt: string;
  title: string;
  providerLabel: string;
  model: string | null;
  validationStatus: "passed" | "warning" | "failed";
  errorCount: number;
  warningCount: number;
  days: number;
  startDate: string | null;
  poiNames: string[];
  /** 没撤回的分享链接；没有为 null */
  share: ShareLink | null;
}

export interface TripItinerary {
  itineraryId: string;
  emphasis: string | null;
  emphasisLabel: string | null;
  /** 新版本在前 */
  versions: TripVersionSummary[];
}

export interface TripConversation {
  conversationId: string;
  /** 这段对话最近一个版本的时间 */
  updatedAt: string;
  /** 这段对话里用户的第一句话 */
  request: string | null;
  itineraries: TripItinerary[];
}
