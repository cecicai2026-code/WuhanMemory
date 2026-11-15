/**
 * 把一份行程变成地图上的路线和图钉（/map、分享页、我的行程共用）。
 *
 * 一天：只放这一天的景点（名字前加顺序），路线按交通方式分色。
 * 全部天（"all"）：每天一种颜色，交通方式只用线型区分；图钉写"天-站"。
 * 没通过校验的行程不画。
 */
import type { MapRoute } from "@wuhanmemory/map-core";
import type { ItineraryVersion, PoiSummary } from "@wuhanmemory/shared";
import { dayColor } from "@/app/map/day-colors";

export type ShownDay = number | "all" | null;

export interface PinOverride {
  id: string;
  name: string;
  location: PoiSummary["location"];
}

function shownDaysOf(version: ItineraryVersion | null, shownDay: ShownDay) {
  if (!version || version.validation.status === "failed") return [];
  return version.days.filter((d) => shownDay === "all" || d.dayNumber === shownDay);
}

export function itineraryRoutes(version: ItineraryVersion | null, shownDay: ShownDay): MapRoute[] {
  const all = shownDay === "all";
  return shownDaysOf(version, shownDay).map((d) => ({
    id: `day-${d.dayNumber}`,
    dayNumber: d.dayNumber,
    color: all ? dayColor(d.dayNumber) : undefined,
    lines: d.legs.filter((l) => l.route.polyline.length > 1).map((l) => ({ mode: l.route.mode, path: l.route.polyline })),
  }));
}

/** 没有可画的天时返回 null（地图上放全部景点） */
export function itineraryPins(version: ItineraryVersion | null, shownDay: ShownDay): PinOverride[] | null {
  const days = shownDaysOf(version, shownDay);
  if (!days.length) return null;
  const all = shownDay === "all";
  return days.flatMap((d) =>
    d.stops.map((st, i) => ({
      id: st.poiId,
      // 一天："2 · 黄鹤楼"；全部天："1-2 · 黄鹤楼"（第 1 天第 2 站）
      name: `${all ? `${d.dayNumber}-` : ""}${i + 1} · ${st.name}`,
      location: st.location,
    })),
  );
}
