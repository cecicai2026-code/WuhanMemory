"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, useTransition, type ReactNode } from "react";
import { htmlLang, LANG_COOKIE, LANG_COOKIE_MAX_AGE, makeT, type Lang, type T } from "@/lib/i18n";

interface LangState {
  lang: Lang;
  t: T;
  setLang: (lang: Lang) => void;
  /** 换了语言、服务器还在重做页面时为 true */
  switching: boolean;
}

const LangContext = createContext<LangState>({ lang: "zh", t: makeT("zh"), setLang: () => {}, switching: false });

/**
 * 根 layout 把服务器决定的语言交进来。点切换时：
 * 先写 cookie、马上换掉浏览器组件里的字，再让服务器按新语言重做页面（router.refresh，不整页刷新，立体场景不重建引擎）。
 */
export function LangProvider({ initial, children }: { initial: Lang; children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);
  const [switching, startTransition] = useTransition();
  const router = useRouter();

  // 服务器给的语言变了（例如另一个标签页里切了语言，这一页刷新后）就跟上
  useEffect(() => setLangState(initial), [initial]);

  const setLang = useCallback(
    (next: Lang) => {
      document.cookie = `${LANG_COOKIE}=${next}; path=/; max-age=${LANG_COOKIE_MAX_AGE}; samesite=lax`;
      document.documentElement.lang = htmlLang(next);
      setLangState(next);
      startTransition(() => router.refresh());
    },
    [router]
  );

  const value = useMemo(() => ({ lang, t: makeT(lang), setLang, switching }), [lang, setLang, switching]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): Lang {
  return useContext(LangContext).lang;
}

export function useT(): T {
  return useContext(LangContext).t;
}

export function useLangState(): LangState {
  return useContext(LangContext);
}
