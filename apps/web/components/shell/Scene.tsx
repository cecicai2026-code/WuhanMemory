"use client";

import type { ReactNode } from "react";
import { BrassButton, Label, TextLink, Title } from "@/components/ui";
import { LangToggle } from "@/components/i18n/LangToggle";
import { useT } from "@/components/i18n/LangProvider";
import { Menu } from "./Menu";
import s from "./shell.module.css";

interface SceneProps {
  /** 幕的编号和名称，显示在左上角 */
  scene: { no: string; name: string; en?: { name: string } };
  /** 右上角的计数。只放程序真实数出来的值，没有就不显示 */
  count?: ReactNode;
  /** 页面标题（h1）。不给就由页面自己写 */
  title?: string;
  kicker?: string;
  intro?: ReactNode;
  /** 左下角的返回链接。首页不需要，传 null。不给就是"回到桌面" */
  back?: { href: string; label: string } | null;
  /** 右下角的"开始规划"按钮。地图工作台自己就是目的地，不显示 */
  showPlan?: boolean;
  /** 正好占满一屏（地图工作台用） */
  fit?: boolean;
  /** 右上角菜单前面的东西，例如"普通版 / 立体版"的切换（components/stage/StageProvider.tsx） */
  corner?: ReactNode;
  children: ReactNode;
}

/**
 * 每个页面最外层都包一个 Scene：
 * 左上是当前幕，右上是计数、语言切换和菜单，左下是返回，右下是"开始规划"。
 * 要按语言换字，所以是浏览器组件（页面传进来的 children 仍可以是服务器组件）。
 */
export function Scene({
  scene,
  count,
  title,
  kicker,
  intro,
  back,
  showPlan = true,
  fit,
  corner,
  children
}: SceneProps) {
  const t = useT();
  if (back === undefined) back = { href: "/", label: t("回到桌面", "Back to the desk") };
  return (
    // data-shell-* 给立体场景用：立体场景打开时四角浮在画布上，正文在视觉上隐藏（globals.css 的"立体场景"一节）
    <div className={fit ? `${s.scene} ${s.fit}` : s.scene}>
      <header className={s.top} data-shell-top>
        <span>{t(`第 ${scene.no} 幕 — ${scene.name}`, `Scene ${scene.no} — ${scene.en?.name ?? scene.name}`)}</span>
        <div className={s.topRight}>
          {count ? <span className={s.count}>{count}</span> : null}
          {corner}
          <LangToggle />
          <Menu />
        </div>
      </header>

      <main className={s.main} data-shell-main>
        {title ? (
          <div className={s.head}>
            {kicker ? <Label className={s.kicker}>{kicker}</Label> : null}
            <Title>{title}</Title>
            {intro ? <p className={s.intro}>{intro}</p> : null}
          </div>
        ) : null}
        {children}
      </main>

      {back || showPlan ? (
        <footer className={s.bottom} data-shell-bottom>
          {back ? <TextLink href={back.href}>← {back.label}</TextLink> : <span />}
          {showPlan ? (
            <BrassButton href="/map" round>
              {t("开始规划", "Start planning")}
            </BrassButton>
          ) : null}
        </footer>
      ) : null}
    </div>
  );
}
