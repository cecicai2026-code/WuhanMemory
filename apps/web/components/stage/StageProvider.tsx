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
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { STAGE_READY_TIMEOUT_MS, deviceAllows3D, flatForced, readPref, webglAvailable, writePref } from "@/lib/scene3d/precheck";
import type { StageCommand, StageEngine, StageFailReason, StageRequest, StageState } from "@/lib/scene3d/types";

type Mode = "checking" | "loading" | "on" | "flat";

interface StageContextValue {
  mode: Mode;
  /** 这台设备能不能用立体（不管用户选了什么），决定要不要显示切换按钮 */
  canOffer3D: boolean;
  choose(v: "flat" | "3d"): void;
  request(req: StageRequest): void;
  /** 页面离开时撤回自己的请求（下一个页面没有立体场景时，引擎停下、显示普通版） */
  release(key: string): void;
  /** 让场景做事（换组、选中、进入） */
  command(cmd: StageCommand): void;
  /** 场景最新的状态，配合 useStageState 用 */
  store: StateStore;
}

/** 场景每次选中别的格都会发状态；用一个小仓库存着，只让用到的组件重画 */
class StateStore {
  private state: StageState | null = null;
  private subs = new Set<() => void>();
  set(s: StageState | null) {
    this.state = s;
    this.subs.forEach((f) => f());
  }
  get = () => this.state;
  subscribe = (f: () => void) => {
    this.subs.add(f);
    return () => this.subs.delete(f);
  };
}

/** 读场景的状态（只在立体模式下有值） */
export function useStageState(): StageState | null {
  const stage = useContext(StageContext);
  const store = stage?.store;
  return useSyncExternalStore(store?.subscribe ?? noopSubscribe, store?.get ?? nullState, nullState);
}
const noopSubscribe = () => () => {};
const nullState = () => null;

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
  const ringRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<StageEngine | null>(null);
  const [store] = useState(() => new StateStore());
  const router = useRouter();
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
    store.set(null);
  }, [store]);

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
    // 这个页面没有立体场景（例如还没做的幕）：引擎停着，显示普通版
    if (want3D && !req) {
      engineRef.current?.idle();
      store.set(null);
      if (engineRef.current) {
        setMode("flat");
        setHtmlStage(null);
      }
      return;
    }
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
          engineRef.current = createEngine(containerRef.current, {
            onFail: fallBack,
            debugFps,
            onState: (st) => store.set(st),
            onQuality: (level) => {
              document.documentElement.dataset.stageQuality = level > 0 ? "low" : "full";
            },
            onNavigate: (href) => router.push(href, { scroll: false }),
            ring: ringRef.current!
          });
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
  }, [want3D, req, fallBack, store, router]);

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
      // 试了不行（例如建不出 WebGL）：不再显示切换按钮
      if (!ok) setCanOffer3D(false);
    }
  }, []);

  const request = useCallback((r: StageRequest) => {
    // 同一幕、同一份数据时不重复布置；数据变了（例如地址里的 ?at= 变了）交给这一幕自己更新
    setReq((prev) => (prev && prev.kind === r.kind && prev.key === r.key && prev.data === r.data ? prev : r));
  }, []);

  const release = useCallback((key: string) => {
    setReq((prev) => (prev && prev.key === key ? null : prev));
  }, []);

  const command = useCallback((cmd: StageCommand) => engineRef.current?.command(cmd), []);

  const value = useMemo(() => ({ mode, canOffer3D, choose, request, release, command, store }), [mode, canOffer3D, choose, request, release, command, store]);

  return (
    <StageContext.Provider value={value}>
      <div ref={containerRef} className="stage-canvas" aria-hidden="true" />
      <div ref={ringRef} className="stage-ring" aria-hidden="true" />
      {children}
    </StageContext.Provider>
  );
}

/** 页面放一个，告诉场景要显示哪一幕、用什么数据。不渲染任何东西 */
export function StageScene({ kind, sceneKey: key, data }: { kind: StageRequest["kind"]; sceneKey: string; data: unknown }) {
  const stage = useStage();
  useLayoutEffect(() => {
    stage?.request({ kind, key, data });
    return () => stage?.release(key);
  }, [stage, kind, key, data]);
  return null;
}

/** 右上角"普通版 / 立体版"的切换。设备不能用立体时不显示 */
export function StageToggle({ className = "stage-toggle" }: { className?: string }) {
  const stage = useStage();
  if (!stage || !stage.canOffer3D || stage.mode === "checking") return null;
  const on = stage.mode === "on" || stage.mode === "loading";
  return (
    <button type="button" className={className} onClick={() => stage.choose(on ? "flat" : "3d")} aria-label={on ? "切换到普通版" : "切换到立体版"}>
      {on ? "普通版" : "立体版"}
    </button>
  );
}
