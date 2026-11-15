/**
 * 路线接口返回的数据结构，和后端 apps/api/app/schemas/route.py 对应。
 * GET /api/routes/compare?from=&to= → RouteCompare；GET /api/routes?from=&to=&mode= → Route。
 * 坐标都是 GCJ-02。字段说明见 docs/architecture/api-contracts.md。
 */
import type { GeoPoint } from "./index";

export type RouteMode = "walk" | "transit" | "drive";

export interface RouteCost {
  /** free：步行不花钱；fare：公交地铁票价；taxi：打车费 */
  kind: "free" | "fare" | "taxi";
  amountCny: number | null;
  note: string;
}

export interface Route {
  mode: RouteMode;
  /** ok：有方案；none：高德没给方案；error：没查成 */
  status: "ok" | "none" | "error";
  durationMinutes: number | null;
  distanceMeters: number | null;
  /** 要走的路（米）：步行是全程，公交地铁是换乘和进出站的步行，打车是 0；旧缓存里没有时为 null */
  walkingDistanceMeters?: number | null;
  cost: RouteCost | null;
  /** 公交地铁坐哪几条线 */
  summary: string | null;
  /** 没有方案时的说明 */
  reason: string | null;
  polyline: GeoPoint[];
  source: { provider: "amap"; api: string } | null;
  /** 向高德查询的时间（带时区的 ISO 时间） */
  checkedAt: string | null;
  expiresAt: string | null;
  /** fresh：刚查的；cached：缓存还没过期；stale：缓存过期了、重查失败，先用旧的 */
  cache: "fresh" | "cached" | "stale" | null;
  warning: string | null;
  error: { code: string; message: string } | null;
}

export interface RoutePlace {
  id: string;
  name: string;
  location: GeoPoint;
}

export interface RouteCompare {
  origin: RoutePlace;
  destination: RoutePlace;
  routes: Route[];
}
