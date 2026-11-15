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
import { boundsOf, type MapBounds, type MapInitOptions, type MapMode, type MapPin, type MapProvider, type MapRoute } from "@wuhanmemory/map-core";
import type { AMapInfoWindow, AMapMap, AMapMarker, AMapNamespace, AMapPolyline, LngLatTuple } from "./amap-types";

export const MAP_STYLE = "amap://styles/dark";
const PITCH_3D = 50;
const LOAD_TIMEOUT_MS = 15000;
/** 框住景点时四周留的空白（上、右、下、左，像素）。上面多留，图钉是往上长的 */
const FIT_PADDING: [number, number, number, number] = [70, 50, 40, 50];
/** 卡片在图钉上方多高（像素），和 map.module.css 里图钉的高度对应 */
const CARD_OFFSET_Y = -46;

/** 路线颜色：按交通方式分。板块 5 按天分色时再加一组 */
const LINE_STYLE = {
  walk: { color: "#e9dfc6", dashed: true }, // 纸色虚线
  transit: { color: "#e2c27e", dashed: false }, // 黄铜高光
  drive: { color: "#b4532a", dashed: false }, // 胶片橙
} as const;

export interface AmapProviderOptions {
  jsKey: string;
  /** 后端代理地址，例如 http://localhost:8000/_AMapService */
  serviceHost: string;
  /** 图钉的样式类名，由页面的 CSS 模块提供 */
  classes: { pin: string; pinHead: string; pinLabel: string };
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

  constructor(private readonly opts: AmapProviderOptions) {}

  async mount(container: HTMLElement, options: MapInitOptions): Promise<void> {
    if (!this.opts.jsKey) throw new AmapLoadError("没有配置高德 JS key（apps/web/.env.local 里的 NEXT_PUBLIC_AMAP_JS_KEY）。");
    // 必须在加载高德脚本之前设置
    window._AMapSecurityConfig = { serviceHost: this.opts.serviceHost };
    let AMap: AMapNamespace;
    try {
      const { default: AMapLoader } = await import("@amap/amap-jsapi-loader");
      AMap = (await AMapLoader.load({ key: this.opts.jsKey, version: "2.0" })) as AMapNamespace;
    } catch (err) {
      throw new AmapLoadError(`高德地图脚本加载失败：${err instanceof Error ? err.message : String(err)}。请检查网络和 JS key。`);
    }
    this.AMap = AMap;
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

    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        reject(new AmapLoadError("高德底图 15 秒内没有加载出来。可能是网络问题，或后端没有启动（安全密钥要经过后端）。"));
      }, LOAD_TIMEOUT_MS);
      map.on("complete", () => {
        window.clearTimeout(timer);
        resolve();
      });
    });
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
      el.setAttribute("aria-label", `${pin.name}：打开景点卡片`);
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
            strokeColor: style.color,
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

  focusBounds(bounds: MapBounds): void {
    const { map, AMap } = this;
    if (!map || !AMap) return;
    map.setBounds(new AMap.Bounds(tuple(bounds.southWest), tuple(bounds.northEast)), false, FIT_PADDING);
  }

  /** 框住全部图钉 */
  fitPins(): void {
    const b = boundsOf([...this.markers.values()].map((m) => m.pin.location));
    if (b) this.focusBounds(b);
  }

  destroy(): void {
    this.closeCard();
    this.map?.off("click", this.onMapClick);
    this.map?.destroy();
    this.map = null;
    this.AMap = null;
    this.markers.clear();
    this.lines = [];
  }
}
