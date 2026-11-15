"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { boundsOf, type MapMode, type MapRoute } from "@wuhanmemory/map-core";
import type { PoiSummary } from "@wuhanmemory/shared";
import { Label, Paper, PaperMark, PaperTitle, Soft, Stamp, TextLink } from "@/components/ui";
import { AmapProvider } from "@/lib/map/amap-provider";
import type { PinOverride } from "@/lib/itinerary-map";
import s from "./map.module.css";

const JS_KEY = process.env.NEXT_PUBLIC_AMAP_JS_KEY ?? "";
/** 武汉市中心附近，地图在框住景点之前先放在这里 */
const WUHAN_CENTER = { lng: 114.3055, lat: 30.5928 };
/** 和 map.module.css 的手机断点一致 */
const PHONE_QUERY = "(max-width: 733px)";
/** 底图这么久还没画完，就提示一句"加载得比较慢"，但继续等 */
const SLOW_MS = 15000;

type LoadState = { kind: "loading"; slow: boolean } | { kind: "ready" } | { kind: "error"; message: string };


interface Props {
  pois: PoiSummary[];
  /** 景点接口出错时的说明；地图照样加载，只是没有图钉 */
  poisError: string | null;
  /** 要画在地图上的路线 */
  routes: MapRoute[];
  /** 给了就只放这些图钉（行程里这一天的景点）；null 放全部景点 */
  pins?: PinOverride[] | null;
}

/**
 * 灯箱里的高德地图（设计规范 9.1）：10 个景点的图钉，打开时框住全部景点；
 * 点图钉在上方出现一张索引卡（2026-11-15 Cecilia 选的气泡方式），能跳到地点档案；
 * 旁边的拨杆切换 2D / 3D，手机上默认 2D。
 */
export function MapPanel({ pois, poisError, routes, pins = null }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const providerRef = useRef<AmapProvider | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading", slow: false });
  const [mode, setMode] = useState<MapMode>("2d");
  const [selected, setSelected] = useState<string | null>(null);
  const [cardHost, setCardHost] = useState<HTMLDivElement | null>(null);

  // 加载地图，只做一次
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const initialMode: MapMode = window.matchMedia(PHONE_QUERY).matches ? "2d" : "3d";
    setMode(initialMode);
    setCardHost(document.createElement("div"));

    const provider = new AmapProvider({
      jsKey: JS_KEY,
      // 安全密钥代理：浏览器连网站自己的 /_AMapService，网站转给后端加上安全密钥
      serviceHost: `${window.location.origin}/_AMapService`,
      classes: { pin: s.pin, pinHead: s.pinHead, pinLabel: s.pinLabel },
    });
    let cancelled = false;
    const slowTimer = window.setTimeout(() => {
      setLoad((cur) => (cur.kind === "loading" ? { kind: "loading", slow: true } : cur));
    }, SLOW_MS);
    provider
      .mount(box, { center: WUHAN_CENTER, zoom: 12, mode: initialMode })
      .then(() => {
        window.clearTimeout(slowTimer);
        if (cancelled) return;
        providerRef.current = provider;
        provider.onPinSelect(setSelected);
        setLoad({ kind: "ready" });
      })
      .catch((err: unknown) => {
        window.clearTimeout(slowTimer);
        if (cancelled) return;
        setLoad({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => {
      cancelled = true;
      window.clearTimeout(slowTimer);
      providerRef.current = null;
      provider.destroy();
    };
  }, []);

  // 图钉：地图好了以后放上去，并框住全部图钉（有路线时由下面的路线来定镜头）
  useEffect(() => {
    const provider = providerRef.current;
    if (load.kind !== "ready" || !provider) return;
    provider.setPins(pins ?? pois.map((p) => ({ id: p.id, name: p.name, location: p.location })));
    setSelected(null);
    if (!routes.some((r) => r.lines.length)) provider.fitPins();
    // routes 只用来判断要不要框住图钉，路线变化由下面的 effect 处理
  }, [load, pois, pins]);

  useEffect(() => {
    if (load.kind === "ready") providerRef.current?.setMode(mode);
  }, [load, mode]);

  // 路线：画上去，并把镜头移到正好框住这条路线
  useEffect(() => {
    const provider = providerRef.current;
    if (load.kind !== "ready" || !provider) return;
    provider.setRoutes(routes);
    const bounds = boundsOf(routes.flatMap((r) => r.lines.flatMap((l) => l.path)));
    if (bounds) provider.focusBounds(bounds);
  }, [load, routes]);

  // 卡片：选中图钉时打开，取消选中时关上
  useEffect(() => {
    const provider = providerRef.current;
    if (load.kind !== "ready" || !provider || !cardHost) return;
    if (selected) provider.openCard(selected, cardHost);
    else provider.closeCard();
  }, [load, selected, cardHost]);

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  const poi = selected ? pois.find((p) => p.id === selected) : undefined;

  return (
    <>
      <div className={s.lightbox}>
        <div className={s.glass}>
          <div ref={boxRef} className={s.map} aria-label="武汉地图" role="region" />
          {load.kind === "loading" && (
            <p className={s.notice} role="status">
              <Label>灯箱</Label> 地图加载中……
              {load.slow && (
                <>
                  <br />
                  加载得比较慢。可能是网络慢；如果一直不出来，看看后端有没有启动（地图请求要经过后端加安全密钥）。
                </>
              )}
            </p>
          )}
          {load.kind === "error" && (
            <div className={s.notice} role="alert">
              <Label>地图没有加载出来</Label>
              <p>{load.message}</p>
            </div>
          )}
          {load.kind === "ready" && poisError && (
            <div className={s.notice} role="alert">
              <Label>没有景点</Label>
              <p>{poisError}</p>
            </div>
          )}
        </div>
      </div>
      <div className={s.lever}>
        <Label>2D</Label>
        <button
          className={s.switch}
          type="button"
          role="switch"
          aria-checked={mode === "3d"}
          aria-label="3D 地图"
          disabled={load.kind !== "ready"}
          onClick={() => setMode(mode === "3d" ? "2d" : "3d")}
        >
          <i />
        </button>
        <Label>3D</Label>
      </div>
      {cardHost &&
        poi &&
        createPortal(
          <Paper kind="card" className={s.pinCard} aria-label={`${poi.name}的卡片`}>
            <button className={s.cardClose} type="button" aria-label="关上卡片" onClick={() => setSelected(null)}>
              ×
            </button>
            <PaperMark>{poi.district}</PaperMark>
            <PaperTitle level={3}>{poi.name}</PaperTitle>
            <span className={s.cardFoot}>
              <Soft>资料</Soft>
              <Stamp status={poi.status} />
            </span>
            <TextLink href={`/places/${poi.id}`} onPaper>
              看地点档案 →
            </TextLink>
          </Paper>,
          cardHost,
        )}
    </>
  );
}
