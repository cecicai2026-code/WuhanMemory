import type { RouteColor } from "@wuhanmemory/map-core";

/**
 * "全部天"视图里每天路线的颜色（2026-11-15 Cecilia 选的：黄铜、纸色、胶片橙，超过三天从头轮换）。
 * 这三种颜色在设计规范里没有状态的含义（绿、蓝灰、红是校验和核实状态，不用）。
 */
export const DAY_COLORS: readonly RouteColor[] = ["brass", "paper", "film"];

export const DAY_COLOR_NAMES: Record<RouteColor, { zh: string; en: string }> = {
  brass: { zh: "黄铜", en: "brass" },
  paper: { zh: "纸色", en: "paper" },
  film: { zh: "胶片橙", en: "film orange" },
};

export function dayColor(dayNumber: number): RouteColor {
  return DAY_COLORS[(dayNumber - 1) % DAY_COLORS.length];
}
