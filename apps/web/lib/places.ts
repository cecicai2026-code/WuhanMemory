/**
 * 地点档案的数据入口：从后端接口 GET /api/pois、GET /api/pois/{id} 取真实景点数据。
 * 景点资料的原始文件是 data/pois/*.json，后端启动时检查并导入 SQLite（ADR 0003）。
 *
 * 只在服务器端调用（页面是服务器组件），直接连后端（lib/backend.ts）。
 * 照片地址是 /media/… 的相对路径，浏览器从网站自己的地址取，由网站转给后端。
 */
import type { PoiDetail, PoiDetailResponse, PoiList, PoiSummary } from "@wuhanmemory/shared";

import { SERVER_API_BASE as API_BASE } from "./backend";

/** 后端连不上或返回错误 */
export class ApiUnavailableError extends Error {}

async function getJson<T>(path: string): Promise<T | null> {
  let res: Response;
  try {
    // 状态和日期有关（过没过期），每次都现取，不缓存
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiUnavailableError(`连不上后端 ${API_BASE}`);
  }
  if (res.status === 404) return null;
  if (!res.ok) throw new ApiUnavailableError(`后端返回 ${res.status}`);
  return (await res.json()) as T;
}

export async function listPlaces(): Promise<PoiList> {
  return (await getJson<PoiList>("/api/pois")) ?? { asOf: "", pois: [] };
}

export async function getPlace(id: string): Promise<PoiDetailResponse | null> {
  return getJson<PoiDetailResponse>(`/api/pois/${encodeURIComponent(id)}`);
}

export function photoUrl(url: string | null): string | null {
  // 照片是 /media/… 的相对路径，浏览器从网站自己的地址取，由网站转给后端
  return url;
}

/** 有哪些区、每个区几个景点，按清单里出现的顺序 */
export function listDistricts(pois: PoiSummary[]): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const p of pois) counts.set(p.district, (counts.get(p.district) ?? 0) + 1);
  return [...counts].map(([name, count]) => ({ name, count }));
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** 纸页上的条目，对应 PoiDetail 的字段（设计规范 8.3 的表） */
export type FieldKey =
  | "intro"
  | "history"
  | "address"
  | "openingHours"
  | "ticket"
  | "reservation"
  | "recommendedDurationMinutes"
  | "bestTime"
  | "transport"
  | "payment"
  | "photoSpots"
  | "reviews"
  | "photos"
  | "food";

export interface Theme {
  /** 页面内的锚点 */
  id: string;
  name: string;
  fields: Array<{ key: FieldKey; label: string }>;
}

/** 每个景点的四个主题，以及每个主题下有哪些条目 */
export const THEMES: Theme[] = [
  {
    id: "overview",
    name: "景点概览",
    fields: [
      { key: "intro", label: "简介" },
      { key: "history", label: "历史文化" },
      { key: "address", label: "地址" },
      { key: "openingHours", label: "开放时间" },
      { key: "ticket", label: "票价" },
      { key: "reservation", label: "是否需要预约" }
    ]
  },
  {
    id: "tips",
    name: "游玩建议",
    fields: [
      { key: "recommendedDurationMinutes", label: "建议游玩时长" },
      { key: "bestTime", label: "适合去的时段" },
      { key: "transport", label: "怎么去" },
      { key: "payment", label: "支付方式" },
      { key: "photoSpots", label: "拍照机位" },
      { key: "reviews", label: "去过的人说" }
    ]
  },
  {
    id: "gallery",
    name: "景点图册",
    fields: [{ key: "photos", label: "照片" }]
  },
  {
    id: "food",
    name: "周边美食",
    fields: [{ key: "food", label: "店名或小吃" }]
  }
];

export type { PoiDetail, PoiList, PoiSummary };
