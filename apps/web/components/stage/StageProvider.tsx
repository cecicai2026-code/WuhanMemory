"use client";

/**
 * 立体场景和普通网页版的切换（设计规范第 15 节第 2、11 条）。
 *
 * 页面照常由服务器输出普通版；StageProvider 包在外面，判断能不能用立体：
 * 设备条件（能悬停、宽度不小于 734、没开减弱动效）、用户没选普通版、地址没带 ?flat=1、能建 WebGL。
 * 都满足时动态加载引擎（lib/scene3d/engine.ts，three.js 只在这时下载），等这一幕准备好，
 * 再把 <html> 的 data-stage 设成 "on"：画布显示出来，普通版的正文在视觉上隐藏，但读屏软件照样读、键盘照样能停在上面。
 * 6 秒没准备好、加载失败、出错、WebGL 丢失、太卡，都退回普通版（data-stage="flat"）。
 *
 * 地点档案的三幕共用一个 StageProvider（放在 app/places/layout.tsx），换页时不卸载；
 * 每个页面用 <StageScene> 告诉它要显示哪一幕、用什么数据。
 */
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { STAGE_READY_TIMEOUT_MS, deviceAllows3D, flatForced, readPref, webglAvailable, writePref } from "@/lib/scene3d/precheck";
import type { StageEngine, StageFailReason, StageRequest } from "@/lib/scene3d/types";

type Mode = "checking" | "loading" | "on" | "flat";

interface StageContextValue {
  mode: Mode;
  /** 这台设备能不能用立体（不管用户选了什么），决定要不要显示切换按钮 */
  canOffer3D: boolean;
  choose(v: "flat" | "3d"): void;
  request(req: StageRequest): void;
}

const StageContext = createContext<StageContextValue | null>(null);

export function useStage() {
  return useContext(StageContext);
}

function setHtmlStage(v: "pending" | "on" | null) {
  const d = document.documentElement;
  if (v) d.setAttribute("data-stage", v);
  else d.setAttribute("data-stage", "flat");
}

export function StageProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("checking");
  const [canOffer3D, setCanOffer3D] = useState(false);
  const [want3D, setWant3D] = useState(false);
  const [req, setReq] = useState<StageRequest | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<StageEngine | null>(null);
  const reasonRef = useRef<string | null>(null);

  // 判断能不能用立体。在画出来之前做，免得普通版闪一下
  useLayoutEffect(() => {
    const evaluate = () => {
      const device = deviceAllows3D();
      const gl = device && webglAvailable();
      setCanOffer3D(gl);
      const want = gl && !flatForced() && readPref() !== "flat";
      setWant3D(want);
      if (!want) {
        setMode("flat");
        setHtmlStage(null);
      }
    };
    evaluate();
    // 窗口变窄、换成触屏、打开减弱动效时重新判断
    const queries = ["(hover: hover) and (pointer: fine)", "(prefers-reduced-motion: reduce)", "(min-width: 734px)"].map((q) => window.matchMedia(q));
    queries.forEach((q) => q.addEventListener("change", evaluate));
    return () => queries.forEach((q) => q.removeEventListener("change", evaluate));
  }, []);

  const teardown = useCallback(() => {
    engineRef.current?.dispose();
    engineRef.current = null;
  }, []);

  const fallBack = useCallback(
    (reason: StageFailReason | string, detail?: unknown) => {
      reasonRef.current = reason;
      if (process.env.NODE_ENV !== "production") console.warn("[stage] 退回普通版：", reason, detail ?? "");
      teardown();
      setMode("flat");
      setHtmlStage(null);
      document.documentElement.dataset.stageReason = reason;
    },
    [teardown]
  );

  // 要用立体、页面也说了要哪一幕：加载引擎（第一次）并显示这一幕
  useEffect(() => {
    if (!want3D || !req) return;
    let cancelled = false;
    const firstTime = !engineRef.current;
    if (firstTime) {
      setMode("loading");
      setHtmlStage("pending");
    }
    const timer = firstTime ? window.setTimeout(() => !cancelled && fallBack("timeout"), STAGE_READY_TIMEOUT_MS) : 0;

    (async () => {
      try {
        if (!engineRef.current) {
          const { createEngine } = await import("@/lib/scene3d/engine");
          if (cancelled || !containerRef.current) return;
          const debugFps = new URLSearchParams(window.location.search).get("debug") === "fps";
          engineRef.current = createEngine(containerRef.current, { onFail: fallBack, debugFps });
        }
        await engineRef.current.show(req);
        if (cancelled) return;
        window.clearTimeout(timer);
        setMode("on");
        setHtmlStage("on");
      } catch (err) {
        if (!cancelled) fallBack(err instanceof Error && /chunk|import|fetch/i.test(err.message) ? "load-error" : "init-error", err);
      }
    })();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [want3D, req, fallBack]);

  // 不用立体了（用户选了普通版、窗口变窄）：关掉引擎
  useEffect(() => {
    if (!want3D) teardown();
  }, [want3D, teardown]);

  // 离开有立体场景的页面时关掉引擎，并把 <html> 恢复成普通版
  useEffect(
    () => () => {
      teardown();
      document.documentElement.removeAttribute("data-stage");
    },
    [teardown]
  );

  const choose = useCallback((v: "flat" | "3d") => {
    writePref(v);
    if (v === "flat") {
      setWant3D(false);
      setMode("flat");
      setHtmlStage(null);
    } else {
      const ok = deviceAllows3D() && webglAvailable();
      setWant3D(ok);
    }
  }, []);

  const request = useCallback((r: StageRequest) => {
    setReq((prev) => (prev && prev.kind === r.kind && prev.key === r.key ? prev : r));
  }, []);

  const value = useMemo(() => ({ mode, canOffer3D, choose, request }), [mode, canOffer3D, choose, request]);

  return (
    <StageContext.Provider value={value}>
      <div ref={containerRef} className="stage-canvas" aria-hidden="true" />
      {children}
    </StageContext.Provider>
  );
}

/** 页面放一个，告诉场景要显示哪一幕、用什么数据。不渲染任何东西 */
export function StageScene(props: StageRequest) {
  const stage = useStage();
  const { kind, key, data } = props;
  useLayoutEffect(() => {
    stage?.request({ kind, key, data });
    // data 是服务器给的，同一个 key 的 data 不会变
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, kind, key]);
  return null;
}

/** 右上角"普通版 / 立体版"的切换。设备不能用立体时不显示 */
export function StageToggle({ className }: { className?: string }) {
  const stage = useStage();
  if (!stage || !stage.canOffer3D || stage.mode === "checking") return null;
  const on = stage.mode === "on" || stage.mode === "loading";
  return (
    <button type="button" className={className} onClick={() => stage.choose(on ? "flat" : "3d")} aria-label={on ? "切换到普通版" : "切换到立体版"}>
      {on ? "普通版" : "立体版"}
    </button>
  );
}
