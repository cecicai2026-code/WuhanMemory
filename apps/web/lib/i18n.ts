/**
 * 中英双语（2026-11-15，Cecilia 定：同一个网址，语言记在 cookie 里；第一次来按浏览器语言猜）。
 *
 * 写法：中英两句话写在一起，t("中文", "English")。不用"键名 → 字典"的方式，
 * 是为了改文案时两种语言就在眼前，不会只改一边。
 *
 * 服务器组件用 lib/i18n-server.ts 的 getT()；浏览器组件用 components/i18n/LangProvider.tsx 的 useT()。
 * 这个文件两边都能用，不引用任何只在一边才有的东西。
 */
export type Lang = "zh" | "en";

export const LANGS: Lang[] = ["zh", "en"];
export const LANG_COOKIE = "wm-lang";
/** cookie 保存一年 */
export const LANG_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function isLang(v: unknown): v is Lang {
  return v === "zh" || v === "en";
}

/**
 * 决定用哪种语言：用户点过切换（cookie）就听用户的；
 * 没点过就看浏览器的首选语言，首选是中文显示中文，其他显示英文；什么都没有时用中文。
 */
export function pickLang(cookie: string | undefined | null, acceptLanguage: string | undefined | null): Lang {
  if (isLang(cookie)) return cookie;
  const first = acceptLanguage?.split(",")[0]?.trim().toLowerCase();
  if (!first) return "zh";
  return first.startsWith("zh") ? "zh" : "en";
}

export type T = <A>(zh: A, en: A) => A;

export function makeT(lang: Lang): T {
  return (zh, en) => (lang === "en" ? en : zh);
}

/** <html lang> 的值 */
export function htmlLang(lang: Lang): string {
  return lang === "en" ? "en" : "zh-CN";
}
