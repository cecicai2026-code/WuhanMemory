/**
 * 立体场景的引擎：一个渲染器、一个每帧循环，轮流显示某一幕。
 * 只在浏览器里、确定要用立体时才被动态加载（components/stage/StageProvider.tsx），
 * 所以 three.js 不会进 /map 等页面的包。
 *
 * 每一幕是一个 Act（./acts/ 下各一个文件，也是按需加载）。地点档案三幕共用一个引擎：
 * 引擎放在 app/places/layout.tsx 里，换页时不卸载，三幕之间可以做物件飞过去的转场。
 *
 * 帧率：每帧记下用时。显示一幕 2 秒后开始算，最近 2 秒平均低于 40 帧就降一级画质
 * （像素比降到 1、阴影图变小、关颗粒和灯光跟随）；降级 3 秒后仍低于 24 帧，就告诉外面退回普通版。
 */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { disposeShared, setMaxAnisotropy } from "./common";
import type { CreateEngine, EngineHooks, StageCommand, StageEngine, StageKind, StageRequest, StageState } from "./types";

/** 每一幕给引擎的东西 */
export interface Act {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  /** 布置好、要用的贴图都准备好时完成 */
  ready: Promise<void>;
  /** 同一幕换了数据（例如地址里换了景点）。返回 false 表示这一幕处理不了，要重建 */
  update(req: StageRequest): boolean;
  step(dt: number): void;
  resize(w: number, h: number): void;
  setQuality(level: number): void;
  /** 网页让这一幕做的事（换组、选中、进入……） */
  command?(cmd: StageCommand): void;
  dispose(): void;
}

export interface ActEnv {
  renderer: THREE.WebGLRenderer;
  /** 鼠标在画面上的位置，-1 到 1（y 向下为正，和样片一样） */
  mouse: THREE.Vector2;
  /** 给射线检测用的位置（y 向上为正）。鼠标不在画面上时是 (9, 9) */
  ndc: THREE.Vector2;
  quality: number;
  environment: THREE.Texture;
  width(): number;
  height(): number;
  /** 这一幕现在是否在屏幕上（页面没有立体场景时引擎停着，滚轮等不该响应） */
  active(): boolean;
  emit(state: StageState): void;
  navigate(href: string, opts?: { curtain?: boolean }): void;
  /** 悬停时物件下方的名字：传文字和屏幕坐标（名字的上沿中点），传 null 隐藏 */
  tag(t: { text: string; x: number; y: number } | null): void;
  /** 键盘聚焦时的黄铜框：传屏幕上的矩形，传 null 隐藏 */
  ring(rect: { x: number; y: number; w: number; h: number } | null): void;
}

export type ActFactory = (env: ActEnv, req: StageRequest) => Act;

/** 每一幕的代码分开打包，用到哪一幕才下载哪一幕 */
const ACTS: Partial<Record<StageKind, () => Promise<ActFactory>>> = {
  rolls: () => import("./acts/rolls").then((m) => m.createRolls),
  line: () => import("./acts/line").then((m) => m.createLine),
  sheet: () => import("./acts/sheet").then((m) => m.createSheet)
};

/** 舞台：主灯（暖白、上方偏左）和暗房红的补光。每一幕的灯位不同，参数照样片 */
export function addLights(
  scene: THREE.Scene,
  { lampPos = [-3, 10, 10], lampTarget = [0.4, 1.4, 0], lampPower = 7.4, lampAngle = 0.66 }: Partial<Record<"lampPos" | "lampTarget", [number, number, number]> & Record<"lampPower" | "lampAngle", number>> = {}
) {
  scene.background = new THREE.Color(0x070504);
  scene.fog = new THREE.Fog(0x070504, 26, 50);
  scene.add(new THREE.HemisphereLight(0xffb48a, 0x1a0806, 0.1));
  const lamp = new THREE.SpotLight(0xffd6a0, lampPower, 0, lampAngle, 0.9, 0);
  lamp.position.set(...lampPos);
  lamp.target.position.set(...lampTarget);
  lamp.castShadow = true;
  lamp.shadow.mapSize.set(2048, 2048);
  lamp.shadow.bias = -0.00025;
  lamp.shadow.normalBias = 0.02;
  lamp.shadow.radius = 8;
  scene.add(lamp, lamp.target);
  const safelight = new THREE.PointLight(0xff3b1e, 1.0, 0, 0);
  safelight.position.set(11, 4.5, 4);
  scene.add(safelight);
  return { lamp, safelight };
}

/** 降级时把阴影图变小 */
export function applyShadowQuality(lamp: THREE.SpotLight, level: number) {
  const size = level > 0 ? 1024 : 2048;
  if (lamp.shadow.mapSize.x === size) return;
  lamp.shadow.mapSize.set(size, size);
  lamp.shadow.map?.dispose();
  lamp.shadow.map = null;
}

export const createEngine: CreateEngine = (container: HTMLElement, hooks: EngineHooks): StageEngine => {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  const basePixelRatio = Math.min(window.devicePixelRatio, 2);
  renderer.setPixelRatio(basePixelRatio);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.domElement.setAttribute("aria-hidden", "true");
  container.appendChild(renderer.domElement);
  setMaxAnisotropy(renderer.capabilities.getMaxAnisotropy());

  const pmrem = new THREE.PMREMGenerator(renderer);
  const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const size = () => ({ w: container.clientWidth || window.innerWidth, h: container.clientHeight || window.innerHeight });
  let { w, h } = size();
  renderer.setSize(w, h);

  const env: ActEnv = {
    renderer,
    mouse: new THREE.Vector2(0, 0),
    ndc: new THREE.Vector2(9, 9),
    quality: 0,
    environment,
    width: () => w,
    height: () => h,
    active: () => !idle && !disposed && !failed,
    emit: (st) => hooks.onState(st),
    navigate: (href, opts) => hooks.onNavigate(href, opts?.curtain ?? true),
    tag: (t) => {
      const el = hooks.tag;
      if (!t) {
        el.style.opacity = "0";
        return;
      }
      if (el.textContent !== t.text) el.textContent = t.text;
      el.style.opacity = "1";
      el.style.transform = `translate(${t.x}px, ${t.y}px) translateX(-50%)`;
    },
    ring: (r) => {
      const el = hooks.ring;
      if (!r) {
        el.style.opacity = "0";
        return;
      }
      el.style.opacity = "1";
      el.style.transform = `translate(${r.x}px, ${r.y}px)`;
      el.style.width = `${r.w}px`;
      el.style.height = `${r.h}px`;
    }
  };

  let act: Act | null = null;
  let actKind: StageKind | null = null;
  let disposed = false;
  let failed = false;
  let idle = false;

  const fail: EngineHooks["onFail"] = (reason, detail) => {
    if (failed || disposed) return;
    failed = true;
    hooks.onFail(reason, detail);
  };

  const onLost = (e: Event) => {
    e.preventDefault();
    fail("context-lost");
  };
  renderer.domElement.addEventListener("webglcontextlost", onLost);

  const onPointer = (e: PointerEvent) => {
    env.mouse.set((e.clientX / w) * 2 - 1, (e.clientY / h) * 2 - 1);
    env.ndc.set(env.mouse.x, -env.mouse.y);
  };
  const onLeave = () => env.ndc.set(9, 9);
  window.addEventListener("pointermove", onPointer);
  document.documentElement.addEventListener("pointerleave", onLeave);

  const ro = new ResizeObserver(() => {
    ({ w, h } = size());
    renderer.setSize(w, h);
    act?.resize(w, h);
  });
  ro.observe(container);

  /* ---------- 帧率和降级 ---------- */
  let frames: number[] = [];
  let measureFrom = Infinity;
  let downgradedAt = Infinity;
  const meter = hooks.debugFps ? makeMeter(container) : null;

  function resetMeasure(delay: number) {
    frames = [];
    measureFrom = performance.now() + delay;
  }
  function measure(now: number, dt: number) {
    if (now < measureFrom) return;
    frames.push(dt);
    let sum = 0;
    for (let i = frames.length - 1; i >= 0; i--) {
      sum += frames[i];
      if (sum >= 2) {
        frames = frames.slice(i);
        break;
      }
    }
    if (sum < 2) return;
    const fps = frames.length / sum;
    if (env.quality === 0 && fps < 40) {
      env.quality = 1;
      renderer.setPixelRatio(1);
      cache.forEach((a) => a.setQuality(1));
      hooks.onQuality?.(1);
      downgradedAt = now;
      resetMeasure(500);
    } else if (env.quality === 1 && now - downgradedAt > 3000 && fps < 24) {
      fail("too-slow", { fps: Math.round(fps) });
    }
  }
  // 页面切到后台时浏览器暂停动画，回来时重新算，不把暂停当成卡顿
  const onVisibility = () => {
    if (!document.hidden) resetMeasure(1000);
  };
  document.addEventListener("visibilitychange", onVisibility);

  /* ---------- 每一帧 ---------- */
  let last = performance.now();
  let raf = 0;
  function frame(now: number) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.05);
    const rawDt = (now - last) / 1000;
    last = now;
    if (!act || failed || idle) return;
    try {
      act.step(dt);
      renderer.render(act.scene, act.camera);
    } catch (err) {
      fail("init-error", err);
      return;
    }
    measure(now, rawDt);
    meter?.tick(now, rawDt, renderer, env.quality);
  }
  raf = requestAnimationFrame(frame);

  // 开发时的调试入口（和样片的 __advance 一样）：页面在后台时浏览器停了动画，用它手动推进若干秒再截图
  if (process.env.NODE_ENV !== "production") {
    (window as unknown as { __stage?: unknown }).__stage = {
      advance(seconds: number) {
        if (!act) return;
        for (let i = 0; i < seconds * 60; i++) act.step(1 / 60);
        renderer.render(act.scene, act.camera);
      }
    };
  }

  /** 每种幕留一个，回到上一幕时不用重新布置（三幕来回切、以后的转场都要用） */
  const cache = new Map<StageKind, Act>();

  function switchTo(next: Act, kind: StageKind) {
    if (act !== next) {
      env.ring(null);
      env.tag(null);
      act = next;
      actKind = kind;
      next.resize(w, h);
      next.setQuality(env.quality);
      // 先画一帧，让贴图传到显卡（着色器已经在 show 里编译好了）
      next.step(0);
      renderer.render(next.scene, next.camera);
    }
    idle = false;
    resetMeasure(2000);
  }

  return {
    async show(req) {
      if (disposed) return;
      // 这一幕已经布置过：交给它自己处理新数据（换景点、换主题），处理不了就重建
      const cached = cache.get(req.kind);
      if (cached && cached.update(req)) {
        switchTo(cached, req.kind);
        return;
      }
      if (cached) {
        if (act === cached) act = null;
        cached.dispose();
        cache.delete(req.kind);
      }
      const load = ACTS[req.kind];
      if (!load) throw new Error(`没有这一幕：${req.kind}`);
      const factory = await load();
      if (disposed) return;
      let self: Act | null = null;
      // 每一幕只在自己显示的时候响应滚轮、点击
      const actEnv: ActEnv = { ...env, active: () => act === self && self !== null && !idle && !disposed && !failed };
      const next = factory(actEnv, req);
      self = next;
      next.setQuality(env.quality);
      next.resize(w, h);
      await next.ready;
      // 着色器在后台编译（浏览器支持并行编译时不卡主线程），编好了再换上，换的那一帧不卡
      if (!disposed) await renderer.compileAsync(next.scene, next.camera);
      if (disposed) {
        next.dispose();
        return;
      }
      cache.set(req.kind, next);
      switchTo(next, req.kind);
    },
    command(cmd) {
      act?.command?.(cmd);
    },
    idle() {
      idle = true;
      env.ring(null);
      env.tag(null);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onPointer);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      cache.forEach((a) => a.dispose());
      cache.clear();
      act = null;
      meter?.remove();
      environment.dispose();
      pmrem.dispose();
      disposeShared();
      renderer.dispose();
      renderer.domElement.remove();
    }
  };
};

/** 地址带 ?debug=fps 时左下角的小计数器：帧率、每帧的绘制次数、显存里的贴图和几何体、画质等级 */
function makeMeter(container: HTMLElement) {
  const el = document.createElement("div");
  el.style.cssText =
    "position:fixed;left:8px;top:50%;z-index:60;padding:6px 8px;background:rgba(7,5,4,.85);border:1px solid #6e5326;color:#e9dfc6;font:11px/1.5 'IBM Plex Mono',monospace;pointer-events:none;white-space:pre";
  container.parentElement?.appendChild(el);
  let acc = 0,
    n = 0,
    lastShow = 0;
  return {
    tick(now: number, dt: number, r: THREE.WebGLRenderer, quality: number) {
      acc += dt;
      n++;
      if (now - lastShow < 500) return;
      lastShow = now;
      const fps = acc > 0 ? n / acc : 0;
      acc = 0;
      n = 0;
      el.textContent = `${fps.toFixed(0)} fps\ndraw ${r.info.render.calls}\ntex ${r.info.memory.textures} geo ${r.info.memory.geometries}\nquality ${quality}`;
    },
    remove() {
      el.remove();
    }
  };
}
