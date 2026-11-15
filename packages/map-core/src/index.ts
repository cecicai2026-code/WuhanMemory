/**
 * 地图 provider 的接口。页面只通过这个接口操作地图，不直接碰高德的对象，
 * 以后换成 Mapbox、Cesium 时只要新写一个实现（见 docs/architecture/system-architecture.md）。
 *
 * 坐标一律是 GCJ-02（高德、景点资料都用这个）。换成用 WGS-84 的地图时，在那个 provider 里转换。
 */
import type { GeoPoint } from "@wuhanmemory/shared";

export type MapMode = "2d" | "3d";

export interface MapBounds {
  northEast: GeoPoint;
  southWest: GeoPoint;
}

export interface MapInitOptions {
  center: GeoPoint;
  zoom: number;
  mode: MapMode;
}

/** 地图上的一个图钉 */
export interface MapPin {
  id: string;
  name: string;
  location: GeoPoint & { coordSystem: "GCJ-02" };
}

/** 路线上的一段：一种交通方式和它的折线 */
export interface MapRouteLine {
  mode: "walk" | "transit" | "drive";
  path: GeoPoint[];
}

/**
 * 按天分色时用的颜色名（设计规范 9.1，2026-11-15 Cecilia 选的：黄铜、纸色、胶片橙轮换）。
 * 只给颜色名，具体色值由各家地图 provider 对着设计规范的变量取。
 */
export type RouteColor = "brass" | "paper" | "film";

/** 一条路线。dayNumber 是第几天，两点之间的临时路线为 null */
export interface MapRoute {
  id: string;
  dayNumber: number | null;
  /** 给了就整条路线用这个颜色（"全部天"视图按天分色），交通方式只用线型区分（步行虚线）；不给就按交通方式分色 */
  color?: RouteColor;
  lines: MapRouteLine[];
}

export interface MapProvider {
  /** 加载地图。失败时 reject，错误信息给人看 */
  mount(container: HTMLElement, options: MapInitOptions): Promise<void>;
  setMode(mode: MapMode): void;
  /** 换掉全部图钉 */
  setPins(pins: MapPin[]): void;
  /** 用户点了某个图钉（id），或点了地图空白处（null） */
  onPinSelect(handler: (pinId: string | null) => void): void;
  /** 在图钉上方打开一张卡片，卡片的内容由页面自己画好传进来 */
  openCard(pinId: string, content: HTMLElement): void;
  closeCard(): void;
  /** 换掉全部路线 */
  setRoutes(routes: MapRoute[]): void;
  focusBounds(bounds: MapBounds): void;
  destroy(): void;
}

/** 正好框住这些点的范围。没有点时返回 null */
export function boundsOf(points: GeoPoint[]): MapBounds | null {
  if (points.length === 0) return null;
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  for (const p of points) {
    minLng = Math.min(minLng, p.lng);
    maxLng = Math.max(maxLng, p.lng);
    minLat = Math.min(minLat, p.lat);
    maxLat = Math.max(maxLat, p.lat);
  }
  return { southWest: { lng: minLng, lat: minLat }, northEast: { lng: maxLng, lat: maxLat } };
}
