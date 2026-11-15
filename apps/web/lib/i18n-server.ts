/**
 * 服务器组件取当前语言（lib/i18n.ts 说明了规则）。
 * 读 cookie 和请求头会让页面每次请求时现做，不再预先生成；本站页面本来就每次现取后端数据，没有影响。
 */
import { cookies, headers } from "next/headers";
import { LANG_COOKIE, makeT, pickLang, type Lang, type T } from "./i18n";

export async function getLang(): Promise<Lang> {
  const [c, h] = await Promise.all([cookies(), headers()]);
  return pickLang(c.get(LANG_COOKIE)?.value, h.get("accept-language"));
}

export async function getT(): Promise<T> {
  return makeT(await getLang());
}
