/**
 * 后端地址（2026-11-15，为上线做的改动，见 docs/operations/deploy-hk.md）。
 *
 * 浏览器只连网站自己的地址：/api、/_AMapService、/media 由网站转给后端
 * （本机开发时是 next.config.ts 的 rewrites，服务器上是 Caddy）。所以浏览器里的请求都用相对路径。
 * 服务器端（页面在服务器上取数据时）直接连后端：API_BASE_URL，默认 http://localhost:8000。
 */
import { browserLang, makeT, type Lang } from "./i18n";

export const SERVER_API_BASE = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** 连不上后端时给人看的话。开发时附上启动命令，上线后只说稍后再试 */
export function backendDownMessage(lang: Lang = browserLang()): string {
  const t = makeT(lang);
  return process.env.NODE_ENV === "development"
    ? t("连不上后端。先启动后端：corepack pnpm dev:api", "Can't reach the backend. Start it first: corepack pnpm dev:api")
    : t("网站的后台暂时连不上，请稍后再试。", "The site's backend can't be reached right now. Please try again later.");
}

/** 后端返回了错误、又没有说明时的一句话 */
export function backendStatusMessage(status: number, lang: Lang = browserLang()): string {
  return makeT(lang)(`后端返回 ${status}`, `The backend returned ${status}`);
}
