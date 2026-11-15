/**
 * 地点档案的数据入口：从后端接口 GET /api/pois、GET /api/pois/{id} 取真实景点数据。
 * 景点资料的原始文件是 data/pois/*.json，后端启动时检查并导入 SQLite（ADR 0003）。
 *
 * 只在服务器端调用（页面是服务器组件），直接连后端（lib/backend.ts）。
 * 照片地址是 /media/… 的相对路径，浏览器从网站自己的地址取，由网站转给后端。
 */
import type { PoiDetail, PoiDetailResponse, PoiList, PoiSummary } from "@wuhanmemory/shared";

import { SERVER_API_BASE as API_BASE } from "./backend";
import type { Lang, T } from "./i18n";

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

/** lang 是 en 时，后端把景点资料里的文字换成英文译文（data/pois/en/，没有译文的条目保留中文） */
export async function listPlaces(lang: Lang): Promise<PoiList> {
  return (await getJson<PoiList>(`/api/pois?lang=${lang}`)) ?? { asOf: "", pois: [] };
}

export async function getPlace(id: string, lang: Lang): Promise<PoiDetailResponse | null> {
  return getJson<PoiDetailResponse>(`/api/pois/${encodeURIComponent(id)}?lang=${lang}`);
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

type Both = { zh: string; en: string };

export interface Theme {
  /** 页面内的锚点 */
  id: string;
  /** 中英两种名称，用 lib/format-poi.ts 的 both(name, t) 取 */
  name: Both;
  fields: Array<{ key: FieldKey; label: Both }>;
}

/** 每个景点的四个主题，以及每个主题下有哪些条目 */
export const THEMES: Theme[] = [
  {
    id: "overview",
    name: { zh: "景点概览", en: "Overview" },
    fields: [
      { key: "intro", label: { zh: "简介", en: "About" } },
      { key: "history", label: { zh: "历史文化", en: "History and culture" } },
      { key: "address", label: { zh: "地址", en: "Address" } },
      { key: "openingHours", label: { zh: "开放时间", en: "Opening hours" } },
      { key: "ticket", label: { zh: "票价", en: "Tickets" } },
      { key: "reservation", label: { zh: "是否需要预约", en: "Booking" } }
    ]
  },
  {
    id: "tips",
    name: { zh: "游玩建议", en: "Visiting tips" },
    fields: [
      { key: "recommendedDurationMinutes", label: { zh: "建议游玩时长", en: "Suggested time" } },
      { key: "bestTime", label: { zh: "适合去的时段", en: "Best time to go" } },
      { key: "transport", label: { zh: "怎么去", en: "Getting there" } },
      { key: "payment", label: { zh: "支付方式", en: "Payment" } },
      { key: "photoSpots", label: { zh: "拍照机位", en: "Photo spots" } },
      { key: "reviews", label: { zh: "去过的人说", en: "From people who went" } }
    ]
  },
  {
    id: "gallery",
    name: { zh: "景点图册", en: "Photos" },
    fields: [{ key: "photos", label: { zh: "照片", en: "Photos" } }]
  },
  {
    id: "food",
    name: { zh: "周边美食", en: "Food nearby" },
    fields: [{ key: "food", label: { zh: "店名或小吃", en: "Places and snacks" } }]
  }
];

/** 卡片上的计数，例如"已过期 1 · 待确认 9 · 待补充 4"。全部核实时是空字符串 */
export function countsText(counts: PoiSummary["counts"], t: T): string {
  const { expired, pending, missing } = counts;
  return [
    expired && t(`已过期 ${expired}`, `${expired} expired`),
    pending && t(`待确认 ${pending}`, `${pending} to confirm`),
    missing && t(`待补充 ${missing}`, `${missing} to fill in`)
  ]
    .filter(Boolean)
    .join(" · ");
}

export function isClosed(p: PoiSummary): boolean {
  return p.operatingStatus?.value?.code === "closed-temporarily";
}

/** 占位照片的出处，写在照片旁边（设计规范第 12 节） */
export function photoCredit(photo: PoiSummary["coverPhoto"], t: T): string | null {
  if (!photo?.placeholder) return null;
  const by = photo.license === "third-party-placeholder" ? (photo.author ?? t("来源链接", "source link")) : t("官方页面", "official page");
  return t(`占位照片 · 出处：${by}`, `Placeholder photo · from ${by}`);
}

/** 按地址里的主题 id 找主题（/places/[id]/[主题]），找不到返回 undefined */
export function findTheme(id: string): Theme | undefined {
  return THEMES.find((t) => t.id === id);
}

/**
 * 详情页、主题页要的数据：这个景点的详情，加上全部景点的清单（算第几张、上一个下一个）。
 * 景点不存在时 place 是 null。后端连不上时抛 ApiUnavailableError。
 */
export async function getPlaceWithList(id: string, lang: Lang): Promise<{ place: PoiDetailResponse | null; all: PoiSummary[] }> {
  const [place, list] = await Promise.all([getPlace(id, lang), listPlaces(lang)]);
  return { place, all: list.pois };
}

export type { PoiDetail, PoiList, PoiSummary };
