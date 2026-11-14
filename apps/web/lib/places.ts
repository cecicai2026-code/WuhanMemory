/**
 * 地点档案的数据入口。
 *
 * 板块 1A 这里只有示例清单：10 个景点的名字和所在区，来自旧骨架的清单，
 * 还没有经过 Cecilia 核实。其余资料（简介、开放时间、票价、照片等）一条都没有，
 * 页面上会显示"待补充"，不编内容。
 *
 * 板块 2 把这个文件换成读取真实景点数据；页面只通过下面几个函数取数据，到时不用改页面。
 */
import type { Status } from "@/components/ui";

/** 纸页上的条目（设计规范 8.3 的表） */
export type FieldKey =
  | "intro"
  | "history"
  | "address"
  | "openingHours"
  | "ticket"
  | "reservation"
  | "duration"
  | "bestTime"
  | "transport"
  | "payment"
  | "photoSpots"
  | "reviews"
  | "gallery"
  | "food";

export interface Place {
  id: string;
  name: string;
  district: string;
  /** 已有的资料。没有的条目不出现在这里，页面显示"待补充" */
  fields: Partial<Record<FieldKey, string>>;
  /** 资料来源和核实日期。没有就显示"待补充" */
  source?: string;
  verifiedAt?: string;
  status: Status;
}

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
      { key: "duration", label: "建议游玩时长" },
      { key: "bestTime", label: "适合去的时段" },
      { key: "transport", label: "怎么去" },
      { key: "payment", label: "支付和预约提示" },
      { key: "photoSpots", label: "拍照机位" },
      { key: "reviews", label: "去过的人说" }
    ]
  },
  {
    id: "gallery",
    name: "景点图册",
    fields: [{ key: "gallery", label: "照片" }]
  },
  {
    id: "food",
    name: "周边美食",
    fields: [{ key: "food", label: "店名或小吃" }]
  }
];

function sample(id: string, name: string, district: string): Place {
  return { id, name, district, fields: {}, status: "pending" };
}

/** 示例清单，只有名字和区。板块 2 换成真实数据 */
const PLACES: Place[] = [
  sample("yellow-crane-tower", "黄鹤楼", "武昌区"),
  sample("hubu-alley", "户部巷", "武昌区"),
  sample("tanhualin", "昙华林", "武昌区"),
  sample("hankou-river-beach", "汉口江滩", "江岸区"),
  sample("hubei-museum", "湖北省博物馆", "武昌区"),
  sample("east-lake-tingtao", "东湖听涛景区", "武昌区"),
  sample("wuhan-university", "武汉大学", "武昌区"),
  sample("gude-temple", "古德寺", "江岸区"),
  sample("jianghan-road", "江汉路步行街", "江汉区"),
  sample("lihuangpi-road", "黎黄陂路", "江岸区")
];

/** 现在的数据是不是示例。板块 2 接入真实数据后改成 false */
export const IS_SAMPLE = true;

export function listPlaces(): Place[] {
  return PLACES;
}

export function getPlace(id: string): Place | undefined {
  return PLACES.find((p) => p.id === id);
}

/** 景点在整份清单里的格号，从 1 开始 */
export function frameNo(id: string): number {
  return PLACES.findIndex((p) => p.id === id) + 1;
}

/** 有哪些区、每个区几个景点，按清单里出现的顺序 */
export function listDistricts(): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const p of PLACES) counts.set(p.district, (counts.get(p.district) ?? 0) + 1);
  return [...counts].map(([name, count]) => ({ name, count }));
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}
