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
import { createFlyer } from "@/lib/scene3d/flight";
import type { Flyer, Handoff, Rect } from "@/lib/scene3d/flight";

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
  /** 网页自己要换幕时用：先落黑幕再跳（例如"回到胶卷"） */
  go(href: string, curtain?: boolean): void;
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

/** 幕与幕之间的黑幕：场景让网页跳转时落下，下一幕准备好后揭开 */
function setCurtain(on: boolean) {
  if (on) document.documentElement.dataset.stageCurtain = "on";
  else delete document.documentElement.dataset.stageCurtain;
}

function setHtmlStage(v: "pending" | "on" | null) {
  const d = document.documentElement;
  if (v) d.setAttribute("data-stage", v);
  else d.setAttribute("data-stage", "flat");
}

/**
 * 页面上有几个 StageProvider。从首页点进地点档案时，新的（地点档案的 layout）先挂上、旧的（首页）后卸载，
 * 旧的卸载时不能把新的刚设好的 data-stage 撤掉。
 */
let mountedProviders = 0;
/** 最近挂上的那个 StageProvider。只有它能改 <html> 上的状态（Next 藏起来的旧页面里的那个不能） */
let activeProvider: object | null = null;

export function StageProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("checking");
  const [canOffer3D, setCanOffer3D] = useState(false);
  const [want3D, setWant3D] = useState(false);
  const [req, setReq] = useState<StageRequest | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const tagRef = useRef<HTMLDivElement>(null);
  const flyerElRef = useRef<HTMLDivElement>(null);
  const flyerRef = useRef<Flyer | null>(null);
  /** 上一幕交出来、正等着下一幕接的物件（转场 G4） */
  const pendingRef = useRef<{ h: Handoff; at: number } | null>(null);
  const flyer = useCallback(() => (flyerRef.current ??= createFlyer(flyerElRef.current!)), []);
  const dropHandoff = useCallback(() => {
    pendingRef.current = null;
    flyerRef.current?.cancel();
    delete document.documentElement.dataset.stageArrival;
  }, []);
  const engineRef = useRef<StageEngine | null>(null);
  const [store] = useState(() => new StateStore());
  const router = useRouter();
  const reasonRef = useRef<string | null>(null);

  const me = useRef({});
  useLayoutEffect(() => {
    mountedProviders++;
    activeProvider = me.current;
    return () => {
      mountedProviders--;
      if (activeProvider === me.current) activeProvider = null;
    };
  }, []);
  /** 只有当前的 StageProvider 才改 <html> 上的状态 */
  const html = useCallback((v: "pending" | "on" | null) => {
    if (activeProvider === me.current) setHtmlStage(v);
  }, []);
  const curtainHere = useCallback((on: boolean) => {
    if (activeProvider === me.current) setCurtain(on);
  }, []);

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
        html(null);
      } else if (!engineRef.current) {
        // 从别的页面点进来（不是整页刷新，<head> 里的脚本不会再跑）：在画出来之前就盖上"显影中"的暗幕，免得先闪一下普通版
        html("pending");
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
      html(null);
      curtainHere(false);
      pendingRef.current = null;
      flyerRef.current?.cancel();
      delete document.documentElement.dataset.stageArrival;
      document.documentElement.dataset.stageReason = reason;
    },
    [teardown]
  );

  // 要用立体、页面也说了要哪一幕：加载引擎（第一次）并显示这一幕
  useEffect(() => {
    // 页面还没说要哪一幕：等一会儿，还是没有就揭开暗幕显示普通版
    if (want3D && !req && !engineRef.current) {
      const t = window.setTimeout(() => {
        if (!engineRef.current) {
          setMode("flat");
          html(null);
        }
      }, 1500);
      return () => window.clearTimeout(t);
    }
    // 这个页面没有立体场景：引擎停着，显示普通版
    if (want3D && !req) {
      engineRef.current?.idle();
      store.set(null);
      if (engineRef.current) {
        setMode("flat");
        html(null);
      }
      curtainHere(false);
      if (pendingRef.current) dropHandoff();
      return;
    }
    if (!want3D || !req) return;
    let cancelled = false;
    const firstTime = !engineRef.current;
    if (firstTime) {
      setMode("loading");
      html("pending");
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
            onNavigate: (href, curtain, handoff) => {
              delete document.documentElement.dataset.stageLanded;
              if (handoff) {
                flyer().show(handoff);
                pendingRef.current = { h: handoff, at: performance.now() };
              }
              if (curtain) curtainHere(true);
              router.push(href, { scroll: false });
            },
            tag: tagRef.current!,
            ring: ringRef.current!
          });
        }
        await engineRef.current.show(req);
        if (cancelled) return;
        window.clearTimeout(timer);
        setMode("on");
        html("on");
        // 上一幕交了物件过来：让替身飞到这一幕里对应的位置（照片 → 晾片幕，主题卡 → 纸页幕）
        const p = pendingRef.current;
        pendingRef.current = null;
        if (p && performance.now() - p.at < 8000 && ((p.h.kind === "print" && req.kind === "line") || (p.h.kind === "card" && req.kind === "sheet"))) {
          void arrive(p.h, engineRef.current);
        } else if (p) dropHandoff();
        curtainHere(false);
      } catch (err) {
        if (!cancelled) fallBack(err instanceof Error && /chunk|import|fetch/i.test(err.message) ? "load-error" : "init-error", err);
      }
    })();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [want3D, req, fallBack, store, router, flyer, dropHandoff]);

  /** 替身飞到下一幕里，落地后露出真的物件 */
  async function arrive(h: Handoff, engine: StageEngine) {
    const f = flyer();
    if (h.kind === "print") {
      engine.command({ type: "arrive", id: h.id });
      const t = engine.query({ type: "arrival" }) as { rect: Rect; image: HTMLCanvasElement | null; pad: { top: number; side: number; bottom: number }; rotate: number } | null;
      if (!t) return dropHandoff();
      await f.toPrint(t.rect, t.image, t.pad, t.rotate);
      engine.command({ type: "landed" });
      await f.done();
      return;
    }
    // 主题卡 → 信纸：信纸先藏着（不播落下的动画），替身翻过来落在信纸的位置，再把信纸露出来、条目显影
    document.documentElement.dataset.stageArrival = "card";
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const paper = [...document.querySelectorAll<HTMLElement>("[data-stage-paper]")].find((el) => !el.closest("[hidden]"));
    if (!paper) return dropHandoff();
    const r = paper.getBoundingClientRect();
    const to = { x: r.left, y: r.top, w: r.width, h: Math.max(80, Math.min(r.height, window.innerHeight - r.top - 24)) };
    await f.toSheet(to);
    document.documentElement.dataset.stageLanded = "card";
    delete document.documentElement.dataset.stageArrival;
    await f.done(320);
  }

  // 不用立体了（用户选了普通版、窗口变窄）：关掉引擎
  useEffect(() => {
    if (!want3D) teardown();
  }, [want3D, teardown]);

  // 离开有立体场景的页面时关掉引擎，并把 <html> 恢复成普通版
  useEffect(
    () => () => {
      teardown();
      // 等这一轮更新跑完再看：下一个页面也有立体场景的话，<html> 上的状态交给它，不去撤
      queueMicrotask(() => {
        if (mountedProviders > 0) return;
        document.documentElement.removeAttribute("data-stage");
        setCurtain(false);
      });
    },
    [teardown]
  );

  const choose = useCallback((v: "flat" | "3d") => {
    writePref(v);
    if (v === "flat") {
      setWant3D(false);
      setMode("flat");
      html(null);
    } else {
      const ok = deviceAllows3D() && webglAvailable();
      setWant3D(ok);
      // 试了不行（例如建不出 WebGL）：不再显示切换按钮
      if (!ok) setCanOffer3D(false);
    }
  }, []);

  const request = useCallback((r: StageRequest) => {
    window.clearTimeout(releaseTimer.current);
    // 同一幕、同一份数据时不重复布置；数据变了（例如地址里的 ?at= 变了）交给这一幕自己更新
    setReq((prev) => (prev && prev.kind === r.kind && prev.key === r.key && prev.data === r.data ? prev : r));
  }, []);

  // 页面换了以后，新页面的数据要从服务器取，中间会显示一下"加载中"。这时先别停引擎，
  // 等 1.5 秒：新页面也有立体场景，就直接换过去，不会闪一下普通版
  const releaseTimer = useRef(0);
  const release = useCallback((key: string) => {
    window.clearTimeout(releaseTimer.current);
    releaseTimer.current = window.setTimeout(() => setReq((prev) => (prev && prev.key === key ? null : prev)), 1500);
  }, []);

  const command = useCallback((cmd: StageCommand) => engineRef.current?.command(cmd), []);

  const go = useCallback(
    (href: string, curtain = true) => {
      delete document.documentElement.dataset.stageLanded;
      if (curtain && engineRef.current) curtainHere(true);
      router.push(href, { scroll: false });
    },
    [router]
  );

  const value = useMemo(() => ({ mode, canOffer3D, choose, request, release, command, go, store }), [mode, canOffer3D, choose, request, release, command, go, store]);

  return (
    <StageContext.Provider value={value}>
      <div ref={containerRef} className="stage-canvas" aria-hidden="true" />
      <div ref={ringRef} className="stage-ring" aria-hidden="true" />
      <div ref={tagRef} className="stage-tag" aria-hidden="true" />
      <FocusProxy active={mode === "on"} />
      <div className="stage-curtain" aria-hidden="true" />
      <div ref={flyerElRef} className="stage-flyer" aria-hidden="true" />
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

/**
 * 立体模式下普通版的正文是隐藏的，键盘焦点停在里面时看不见停在哪。
 * 这一条在画面下方写出焦点所在的链接或按钮（例如"来源：湖北省博物馆官网"），场景里对应的物件另有黄铜框。
 */
function FocusProxy({ active }: { active: boolean }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    if (!active) {
      setText(null);
      return;
    }
    const onIn = (e: FocusEvent) => {
      const t = e.target as HTMLElement | null;
      const main = t?.closest?.("[data-shell-main]");
      if (!t || !main || t.closest("[data-stage-show]")) return setText(null);
      const label = (t.getAttribute("aria-label") ?? t.textContent ?? "").replace(/\s+/g, " ").trim();
      // 场景已经在对应的物件周围画了黄铜框（例如景点卡片、主题链接、首页的入口）时不用再写
      window.setTimeout(() => {
        if (document.activeElement !== t) return;
        const ringShown = (document.querySelector(".stage-ring") as HTMLElement | null)?.style.opacity === "1";
        setText(!ringShown && label ? (label.length > 48 ? `${label.slice(0, 48)}……` : label) : null);
      }, 60);
    };
    const onOut = () => setText(null);
    document.addEventListener("focusin", onIn);
    document.addEventListener("focusout", onOut);
    return () => {
      document.removeEventListener("focusin", onIn);
      document.removeEventListener("focusout", onOut);
    };
  }, [active]);
  return (
    <div className="stage-focus" aria-hidden="true" data-on={text ? "" : undefined}>
      {text ? `焦点 · ${text} · 回车打开` : null}
    </div>
  );
}
