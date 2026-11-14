import type { ReactNode } from "react";
import { BrassButton, Label, TextLink, Title } from "@/components/ui";
import { Menu } from "./Menu";
import s from "./shell.module.css";

interface SceneProps {
  /** 幕的编号和名称，显示在左上角 */
  scene: { no: string; name: string };
  /** 右上角的计数。只放程序真实数出来的值，没有就不显示 */
  count?: ReactNode;
  /** 页面标题（h1）。不给就由页面自己写 */
  title?: string;
  kicker?: string;
  intro?: ReactNode;
  /** 左下角的返回链接。首页不需要，传 null */
  back?: { href: string; label: string } | null;
  /** 右下角的"开始规划"按钮。地图工作台自己就是目的地，不显示 */
  showPlan?: boolean;
  /** 正好占满一屏（地图工作台用） */
  fit?: boolean;
  children: ReactNode;
}

/**
 * 每个页面最外层都包一个 Scene：
 * 左上是当前幕，右上是计数和菜单，左下是返回，右下是"开始规划"。
 */
export function Scene({
  scene,
  count,
  title,
  kicker,
  intro,
  back = { href: "/", label: "回到桌面" },
  showPlan = true,
  fit,
  children
}: SceneProps) {
  return (
    <div className={fit ? `${s.scene} ${s.fit}` : s.scene}>
      <header className={s.top}>
        <span>
          第 {scene.no} 幕 — {scene.name}
        </span>
        <div className={s.topRight}>
          {count ? <span className={s.count}>{count}</span> : null}
          <Menu />
        </div>
      </header>

      <main className={s.main}>
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
        <footer className={s.bottom}>
          {back ? <TextLink href={back.href}>← {back.label}</TextLink> : <span />}
          {showPlan ? (
            <BrassButton href="/map" round>
              开始规划
            </BrassButton>
          ) : null}
        </footer>
      ) : null}
    </div>
  );
}
