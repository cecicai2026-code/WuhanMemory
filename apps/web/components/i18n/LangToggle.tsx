"use client";

import { useLangState } from "./LangProvider";
import s from "./lang.module.css";

/**
 * 右上角菜单旁边的黄铜铭牌"中 / EN"（2026-11-15 Cecilia 定）。
 * 当前语言亮，另一个暗；点哪一边就换成哪种语言。每一页都在同一个位置，手机上也在。
 */
export function LangToggle() {
  const { lang, setLang, switching } = useLangState();
  return (
    <div className={s.plate} role="group" aria-label={lang === "en" ? "Language" : "语言"} data-switching={switching || undefined}>
      <button
        type="button"
        lang="zh-CN"
        aria-pressed={lang === "zh"}
        aria-label="中文"
        onClick={() => lang !== "zh" && setLang("zh")}
      >
        中
      </button>
      <span className={s.slash} aria-hidden="true">
        /
      </span>
      <button
        type="button"
        lang="en"
        aria-pressed={lang === "en"}
        aria-label="English"
        onClick={() => lang !== "en" && setLang("en")}
      >
        EN
      </button>
    </div>
  );
}
