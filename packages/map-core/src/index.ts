import type { GeoPoint, MapPoi, RouteSegment } from "@wuhanmemory/shared";

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

export interface MapRoute {
  dayNumber: number;
  segments: RouteSegment[];
}

export interface MapProvider {
  mount(container: HTMLElement, options: MapInitOptions): Promise<void>;
  setMode(mode: MapMode): Promise<void>;
  renderPois(pois: MapPoi[]): void;
  renderRoute(route: MapRoute): void;
  focusBounds(bounds: MapBounds): void;
  destroy(): void;
}
