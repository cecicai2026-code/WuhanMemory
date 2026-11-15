/**
 * 高德 JS API 2.0 的地图 provider，实现 packages/map-core 的 MapProvider 接口。
 *
 * - key：浏览器只拿到 JS key（NEXT_PUBLIC_AMAP_JS_KEY）。安全密钥不在浏览器里：
 *   window._AMapSecurityConfig.serviceHost 指向后端的 /_AMapService，由后端加上安全密钥
 *   （apps/api/app/api/amap_proxy.py）。
 * - 坐标：景点资料和高德都是 GCJ-02，不转换。
 * - 2D / 3D：地图一直用 viewMode "3D" 创建，2D 就是俯仰角 0、不许拖动俯仰和旋转；
 *   3D 是俯仰角 50 度，可以拖动。这样切换时不用重建地图。
 * - 配色：高德自带的"幻影黑"（amap://styles/dark），2026-11-15 Cecilia 选的。
 */
import { boundsOf, type MapBounds, type MapInitOptions, type MapMode, type MapPin, type MapProvider, type MapRoute, type RouteColor } from "@wuhanmemory/map-core";
import type { AMapInfoWindow, AMapMap, AMapMarker, AMapNamespace, AMapPolyline, LngLatTuple } from "./amap-types";
import { makeT, type Lang } from "@/lib/i18n";

export const MAP_STYLE = "amap://styles/dark";
const PITCH_3D = 50;
/** 框住景点时四周留的空白（上、右、下、左，像素）。上面多留，图钉是往上长的 */
const FIT_PADDING: [number, number, number, number] = [70, 50, 40, 50];
/** 卡片在图钉上方多高（像素），和 map.module.css 里图钉的高度对应 */
const CARD_OFFSET_Y = -46;
/** 框住景点或路线时最多放大到这一级，免得两点很近时贴得太近 */
const MAX_FIT_ZOOM = 16;

/** 路线颜色：默认按交通方式分（一天的视图、两点之间的路线） */
const LINE_STYLE = {
  walk: { color: "#e9dfc6", dashed: true }, // 纸色虚线
  transit: { color: "#e2c27e", dashed: false }, // 黄铜高光
  drive: { color: "#b4532a", dashed: false }, // 胶片橙
} as const;

/** "全部天"视图按天分色时的色值，和上面同一组颜色（globals.css 的 --paper、--brass-bright、--film） */
const ROUTE_COLOR: Record<RouteColor, string> = {
  brass: "#e2c27e",
  paper: "#e9dfc6",
  film: "#b4532a",
};

export interface AmapProviderOptions {
  jsKey: string;
  /** 安全密钥代理的完整地址，例如 http://localhost:3000/_AMapService（网站转给后端） */
  serviceHost: string;
  /** 图钉的样式类名，由页面的 CSS 模块提供 */
  classes: { pin: string; pinHead: string; pinLabel: string };
  /** 网站的语言（中英双语）：图钉的读屏说明、出错提示跟着它。
   * 底图上的地名一直是中文：2026-11-15 在浏览器里试过，高德 JS API 2.0 的 lang: "en" 不起作用（默认样式和深色样式都一样） */
  lang: Lang;
}

export class AmapLoadError extends Error {}

function tuple(p: { lng: number; lat: number }): LngLatTuple {
  // 高德要求经纬度不超过 6 位小数
  return [Number(p.lng.toFixed(6)), Number(p.lat.toFixed(6))];
}

export class AmapProvider implements MapProvider {
  private AMap: AMapNamespace | null = null;
  private map: AMapMap | null = null;
  private markers = new Map<string, { marker: AMapMarker; el: HTMLElement; pin: MapPin }>();
  private lines: AMapPolyline[] = [];
  private card: AMapInfoWindow | null = null;
  private selectHandler: (id: string | null) => void = () => {};
  private onMapClick = () => this.selectHandler(null);
  /** destroy() 之后为 true。React 开发模式会挂载两次，第一次的脚本加载完时不能再建地图 */
  private destroyed = false;
  private container: HTMLElement | null = null;

  constructor(private readonly opts: AmapProviderOptions) {}

  private get t() {
    return makeT(this.opts.lang);
  }

  async mount(container: HTMLElement, options: MapInitOptions): Promise<void> {
    if (!this.opts.jsKey) throw new AmapLoadError(this.t("没有配置高德 JS key（apps/web/.env.local 里的 NEXT_PUBLIC_AMAP_JS_KEY）。", "No AMap JS key is set (NEXT_PUBLIC_AMAP_JS_KEY in apps/web/.env.local)."));
    // 必须在加载高德脚本之前设置
    window._AMapSecurityConfig = { serviceHost: this.opts.serviceHost };
    let AMap: AMapNamespace;
    try {
      const { default: AMapLoader } = await import("@amap/amap-jsapi-loader");
      AMap = (await AMapLoader.load({ key: this.opts.jsKey, version: "2.0" })) as AMapNamespace;
    } catch (err) {
      const why = err instanceof Error ? err.message : String(err);
      throw new AmapLoadError(this.t(`高德地图脚本加载失败：${why}。请检查网络和 JS key。`, `The AMap script failed to load: ${why}. Check the network and the JS key.`));
    }
    if (this.destroyed) throw new AmapLoadError(this.t("地图已经关掉了", "The map was closed"));
    this.AMap = AMap;
    this.container = container;
    const map = new AMap.Map(container, {
      center: tuple(options.center),
      zoom: options.zoom,
      viewMode: "3D",
      pitch: options.mode === "3d" ? PITCH_3D : 0,
      mapStyle: MAP_STYLE,
      pitchEnable: options.mode === "3d",
      rotateEnable: options.mode === "3d",
    });
    this.map = map;
    map.on("click", this.onMapClick);

    // 等底图画完。不设超时：网络慢或页面在后台时会久一点，页面上另外提示"加载得比较慢"
    await new Promise<void>((resolve) => map.on("complete", () => resolve()));
  }

  setMode(mode: MapMode): void {
    const map = this.map;
    if (!map) return;
    if (mode === "3d") {
      map.setStatus({ pitchEnable: true, rotateEnable: true });
      map.setPitch(PITCH_3D, false, 600);
    } else {
      map.setRotation(0, false, 600);
      map.setPitch(0, false, 600);
      map.setStatus({ pitchEnable: false, rotateEnable: false });
    }
  }

  setPins(pins: MapPin[]): void {
    const { map, AMap } = this;
    if (!map || !AMap) return;
    this.closeCard();
    map.remove([...this.markers.values()].map((m) => m.marker));
    this.markers.clear();
    const { classes } = this.opts;
    for (const pin of pins) {
      const el = document.createElement("button");
      el.type = "button";
      el.className = classes.pin;
      el.setAttribute("aria-label", this.t(`${pin.name}：打开景点卡片`, `${pin.name}: open the place card`));
      const head = document.createElement("span");
      head.className = classes.pinHead;
      head.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.className = classes.pinLabel;
      label.textContent = pin.name;
      el.append(head, label);
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this.selectHandler(pin.id);
      });
      const marker = new AMap.Marker({ position: tuple(pin.location), content: el, anchor: "bottom-center", title: pin.name });
      this.markers.set(pin.id, { marker, el, pin });
    }
    map.add([...this.markers.values()].map((m) => m.marker));
  }

  onPinSelect(handler: (pinId: string | null) => void): void {
    this.selectHandler = handler;
  }

  openCard(pinId: string, content: HTMLElement): void {
    const { map, AMap } = this;
    const entry = this.markers.get(pinId);
    if (!map || !AMap || !entry) return;
    this.closeCard();
    for (const [id, m] of this.markers) m.el.toggleAttribute("data-selected", id === pinId);
    this.card = new AMap.InfoWindow({
      isCustom: true,
      content,
      anchor: "bottom-center",
      offset: new AMap.Pixel(0, CARD_OFFSET_Y),
      autoMove: true,
    });
    this.card.open(map, tuple(entry.pin.location));
  }

  closeCard(): void {
    this.card?.close();
    this.card = null;
    for (const m of this.markers.values()) m.el.removeAttribute("data-selected");
  }

  setRoutes(routes: MapRoute[]): void {
    const { map, AMap } = this;
    if (!map || !AMap) return;
    if (this.lines.length) map.remove(this.lines);
    this.lines = [];
    for (const route of routes) {
      for (const line of route.lines) {
        if (line.path.length < 2) continue;
        const style = LINE_STYLE[line.mode];
        this.lines.push(
          new AMap.Polyline({
            path: line.path.map(tuple),
            strokeColor: route.color ? ROUTE_COLOR[route.color] : style.color,
            strokeWeight: 5,
            strokeOpacity: 0.95,
            strokeStyle: style.dashed ? "dashed" : "solid",
            strokeDasharray: style.dashed ? [10, 8] : undefined,
            lineJoin: "round",
            lineCap: "round",
            showDir: !style.dashed,
            zIndex: 60,
          }),
        );
      }
    }
    if (this.lines.length) map.add(this.lines);
  }

  /**
   * 缩放到正好框住这个范围。高德的 setBounds / setFitView 只给整数级缩放，框得偏松，
   * 所以这里按墨卡托投影自己算带小数的缩放级别和中心点。
   */
  focusBounds(bounds: MapBounds): void {
    const { map, container } = this;
    if (!map || !container) return;
    const [top, right, bottom, left] = FIT_PADDING;
    const w = Math.max(container.clientWidth - left - right, 40);
    const h = Math.max(container.clientHeight - top - bottom, 40);
    const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
    const sw = bounds.southWest;
    const ne = bounds.northEast;
    const dx = Math.max(((ne.lng - sw.lng) * Math.PI) / 180, 1e-9);
    const dy = Math.max(mercY(ne.lat) - mercY(sw.lat), 1e-9);
    // 缩放级别 z 时，整个世界宽 256 * 2^z 像素，对应 2π 弧度
    const zoom = Math.min(Math.log2((w * 2 * Math.PI) / (256 * dx)), Math.log2((h * 2 * Math.PI) / (256 * dy)), MAX_FIT_ZOOM);
    // 中心点：留白上下不一样多，中心往下挪一点，让图钉（往上长）不出框
    const midY = (mercY(ne.lat) + mercY(sw.lat)) / 2;
    const pxPerRad = (256 * 2 ** zoom) / (2 * Math.PI);
    const centerY = midY + (top - bottom) / 2 / pxPerRad;
    const centerLat = ((2 * Math.atan(Math.exp(centerY)) - Math.PI / 2) * 180) / Math.PI;
    const centerLng = (sw.lng + ne.lng) / 2 + ((((right - left) / 2) / pxPerRad) * 180) / Math.PI;
    map.setZoomAndCenter(zoom, tuple({ lng: centerLng, lat: centerLat }), false, 500);
  }

  /** 框住全部图钉 */
  fitPins(): void {
    const b = boundsOf([...this.markers.values()].map((m) => m.pin.location));
    if (b) this.focusBounds(b);
  }

  destroy(): void {
    this.destroyed = true;
    this.closeCard();
    this.map?.off("click", this.onMapClick);
    this.map?.destroy();
    this.map = null;
    this.AMap = null;
    this.markers.clear();
    this.lines = [];
  }
}
