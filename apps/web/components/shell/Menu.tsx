"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useT } from "@/components/i18n/LangProvider";
import { MENU } from "@/lib/scenes";
import s from "./shell.module.css";

/** 判断菜单里的某一项是不是当前页面。/places/xxx 也算在"地点档案"下 */
function isCurrent(pathname: string, path: string) {
  return path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(`${path}/`);
}

/**
 * 右上角的菜单。板块 1A 是一个普通的链接列表；
 * 板块 1B 再换成设计规范里说的"桌面俯视小图"。
 */
export function Menu() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const root = useRef<HTMLDivElement>(null);
  const t = useT();

  // 打开时：按 Esc 或点菜单以外的地方就关上
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <nav className={s.menu} ref={root} aria-label={t("页面导航", "Site navigation")}>
      <button
        className={s.menuButton}
        type="button"
        aria-expanded={open}
        aria-controls="site-menu"
        onClick={() => setOpen((v) => !v)}
      >
        <span className={s.bars} aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        {t("菜单", "Menu")}
      </button>
      {open ? (
        <ul className={s.panel} id="site-menu">
          {MENU.map((item) => (
            <li key={item.path}>
              <Link
                href={item.path}
                aria-current={isCurrent(pathname, item.path) ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                <span className={s.pageName}>{t(item.page, item.en.page)}</span>
                <span className={s.sceneNo}>
                  {item.no} · {t(item.name, item.en.name)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </nav>
  );
}
