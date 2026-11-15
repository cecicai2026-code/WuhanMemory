"use client";

import { useT } from "./LangProvider";

/**
 * 在不能用 useT() 也拿不到 getT() 的地方（服务器和浏览器两边都会用到的小组件）写一句双语文字：
 * <Tr zh="已核实" en="Verified" />。按当前语言显示其中一句。
 */
export function Tr({ zh, en }: { zh: string; en: string }) {
  return <>{useT()(zh, en)}</>;
}
