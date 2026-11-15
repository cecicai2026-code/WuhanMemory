/**
 * 高德 JS API 2.0 里本项目用到的那一小部分的类型。
 * 官方加载器只给 load() 返回 any，这里写清楚用到的对象，类型检查才能发现拼错。
 * 参考：https://lbs.amap.com/api/javascript-api-v2/documentation
 */

export type LngLatTuple = [number, number];

export interface AMapPixel {
  readonly __pixel: true;
}

export interface AMapBounds {
  readonly __bounds: true;
}

export interface AMapEventTarget {
  on(event: string, handler: (...args: unknown[]) => void): void;
  off(event: string, handler: (...args: unknown[]) => void): void;
}

export interface AMapMap extends AMapEventTarget {
  setPitch(pitch: number, immediately?: boolean, duration?: number): void;
  setRotation(rotation: number, immediately?: boolean, duration?: number): void;
  setStatus(status: { pitchEnable?: boolean; rotateEnable?: boolean }): void;
  setBounds(bounds: AMapBounds, immediately?: boolean, avoid?: [number, number, number, number]): void;
  setMapStyle(style: string): void;
  /** 底图上地名的语言：zh_cn 中文，en 英文，zh_en 中英 */
  setLang(lang: "zh_cn" | "en" | "zh_en"): void;
  setZoomAndCenter(zoom: number, center: LngLatTuple, immediately?: boolean, duration?: number): void;
  add(overlay: unknown | unknown[]): void;
  remove(overlay: unknown | unknown[]): void;
  destroy(): void;
}

export interface AMapMarker extends AMapEventTarget {
  getPosition(): unknown;
}

export interface AMapInfoWindow {
  open(map: AMapMap, position: LngLatTuple): void;
  close(): void;
}

export interface AMapPolyline {
  readonly __polyline: true;
}

export interface AMapNamespace {
  Map: new (
    container: HTMLElement,
    opts: {
      center: LngLatTuple;
      zoom: number;
      viewMode: "2D" | "3D";
      pitch?: number;
      mapStyle?: string;
      pitchEnable?: boolean;
      rotateEnable?: boolean;
      showBuildingBlock?: boolean;
  lang?: "zh_cn" | "en" | "zh_en";
    },
  ) => AMapMap;
  Marker: new (opts: {
    position: LngLatTuple;
    content: HTMLElement;
    anchor?: string;
    title?: string;
    zIndex?: number;
  }) => AMapMarker;
  InfoWindow: new (opts: { isCustom: boolean; content: HTMLElement; anchor?: string; offset?: AMapPixel; autoMove?: boolean }) => AMapInfoWindow;
  Polyline: new (opts: {
    path: LngLatTuple[];
    strokeColor: string;
    strokeWeight: number;
    strokeOpacity?: number;
    strokeStyle?: "solid" | "dashed";
    strokeDasharray?: number[];
    lineJoin?: string;
    lineCap?: string;
    showDir?: boolean;
    zIndex?: number;
  }) => AMapPolyline;
  Bounds: new (southWest: LngLatTuple, northEast: LngLatTuple) => AMapBounds;
  Pixel: new (x: number, y: number) => AMapPixel;
}

declare global {
  interface Window {
    _AMapSecurityConfig?: { serviceHost?: string; securityJsCode?: string };
  }
}
