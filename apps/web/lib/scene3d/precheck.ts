/**
 * 立体场景能不能用的判断（设计规范第 15 节第 2 条）。
 *
 * 服务器总是先输出普通网页版。浏览器里分两步判断：
 * 1. 页面一打开，<head> 里的一小段脚本（PRECHECK_SCRIPT）先做不花时间的判断（宽度、能不能悬停、减弱动效、
 *    用户选过普通版没有）。都满足时给 <html> 加 data-stage="pending"，盖一层"显影中"的暗幕，
 *    免得先看到普通版、再突然换成立体。6.5 秒后还是 pending（比如脚本出错没接上），自己揭开暗幕。
 * 2. React 接手后（components/stage/StageProvider.tsx）再试着建 WebGL、加载场景代码，
 *    成功就是 data-stage="on"，任何一步不行就是 "flat"，显示普通版。
 *
 * 判断规则在这里写一份，<head> 里的脚本和 React 里的判断都用它。
 */

/** 这次访问打开的第一个页面（开场 G6 只在第一个页面播），记在 sessionStorage 里 */
export const FIRST_PAGE_KEY = "wm-first-page";
/** 开场已经播过 */
export const INTRO_DONE_KEY = "wm-intro-done";

/** 首页要不要播开场：这次访问的第一个页面是首页，并且还没播过 */
export function shouldPlayIntro(): boolean {
  try {
    return sessionStorage.getItem(FIRST_PAGE_KEY) === "/" && !sessionStorage.getItem(INTRO_DONE_KEY);
  } catch {
    return false;
  }
}
export function markIntroDone() {
  try {
    sessionStorage.setItem(INTRO_DONE_KEY, "1");
  } catch {
    // 存不了就算了，下次再播一遍
  }
}

/** 普通版 / 立体版的选择记在浏览器里，用这个键 */
export const STAGE_PREF_KEY = "wm-stage";

/** 有立体场景的网址（正则）。每做好一幕加一条 */
export const STAGE_PATHS: string[] = ["^/$", "^/places/?$", "^/places/[^/]+/?$", "^/places/[^/]+/[^/]+/?$"];

/** 这个网址有没有立体场景 */
export function pathHasStage(pathname: string): boolean {
  return STAGE_PATHS.some((p) => new RegExp(p).test(pathname));
}

export type StagePref = "flat" | "3d" | null;

export function readPref(): StagePref {
  try {
    const v = localStorage.getItem(STAGE_PREF_KEY);
    return v === "flat" || v === "3d" ? v : null;
  } catch {
    return null;
  }
}

export function writePref(v: "flat" | "3d"): void {
  try {
    localStorage.setItem(STAGE_PREF_KEY, v);
  } catch {
    // 浏览器不让存（隐私模式等）：这次照样切换，只是下次不记得
  }
}

/** 设备条件：能悬停、宽度够、没开减弱动效。不看用户的选择 */
export function deviceAllows3D(): boolean {
  return (
    window.innerWidth >= 734 &&
    window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** 地址里带 ?flat=1 就直接看普通版（检查退路时用），不改浏览器里记的选择 */
export function flatForced(): boolean {
  return new URLSearchParams(window.location.search).get("flat") === "1";
}

/** 能不能建出 WebGL。建一个临时画布试一下，试完就丢掉 */
export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") ?? c.getContext("webgl");
    if (!gl) return false;
    (gl as WebGLRenderingContext).getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/** <head> 里的脚本。不能 import，所以把上面几条规则原样写成一段字符串 */
export const PRECHECK_SCRIPT = `(function(){try{
try{if(!sessionStorage.getItem(${JSON.stringify(FIRST_PAGE_KEY)}))sessionStorage.setItem(${JSON.stringify(FIRST_PAGE_KEY)},location.pathname);}catch(e){}
var paths=${JSON.stringify(STAGE_PATHS)},p=location.pathname,hit=false;
for(var i=0;i<paths.length;i++){if(new RegExp(paths[i]).test(p))hit=true;}
if(!hit)return;
if(new URLSearchParams(location.search).get('flat')==='1')return;
var pref=null;try{pref=localStorage.getItem(${JSON.stringify(STAGE_PREF_KEY)});}catch(e){}
if(pref==='flat')return;
if(innerWidth<734||!matchMedia('(hover: hover) and (pointer: fine)').matches||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
var d=document.documentElement;d.setAttribute('data-stage','pending');
setTimeout(function(){if(d.getAttribute('data-stage')==='pending')d.setAttribute('data-stage','flat');},6500);
}catch(e){}})();`;

/** 立体场景要在多少毫秒内准备好，超过就留在普通版 */
export const STAGE_READY_TIMEOUT_MS = 6000;
