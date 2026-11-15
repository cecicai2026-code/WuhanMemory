"use client";

/**
 * 首页桌面的立体版（设计规范第 9.4 节）：告诉场景显示桌面，再在画布上面放网页元素：
 * 全景时的大标题，停在某件物件时旁边的说明和入口，底部上下两个黄铜按钮和"第几站 / 共几站"。
 *
 * 键盘和读屏软件用的是普通版的四张入口卡片（还在页面里，只是视觉上隐藏）：
 * Tab 停到某张卡片时镜头去那件物件、物件周围出现黄铜框；回车时镜头推近再进入。
 * 上下方向键、PageUp / PageDown 一站一站走。
 */
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { StageScene, useStage, useStageState } from "@/components/stage/StageProvider";
import { Grain, typingInto } from "@/components/stage/StageBits";
import s from "@/components/stage/stage.module.css";
import type { DeskData } from "@/lib/scene3d/data";
import { markIntroDone, shouldPlayIntro } from "@/lib/scene3d/precheck";
import type { SceneInfo } from "@/lib/scenes";
import { useLang } from "@/components/i18n/LangProvider";
import { makeT } from "@/lib/i18n";

export interface DeskStop {
  scene: SceneInfo;
  object: string;
  title: string;
  text: string;
  action: string;
}

const VIEW_NAMES = {
  zh: ["桌面全景", "胶卷罐", "灯箱", "两台打字机", "笔记本"],
  en: ["The whole desk", "Film canister", "Light box", "Two typewriters", "Notebook"]
};
const pad2 = (n: number) => String(n).padStart(2, "0");

export function DeskStage({ stops }: { stops: DeskStop[] }) {
  const stage = useStage();
  const st = useStageState();
  const on = stage?.mode === "on" && st?.kind === "desk";
  const at = on ? Number(st.at) : 0;
  const n = stops.length + 1;
  const lang = useLang();
  const t = makeT(lang);

  // 开场只在这次访问的第一个页面是首页时播一次（G6）。在浏览器里才知道，所以等挂上以后再算
  const [intro, setIntro] = useState<boolean | null>(null);
  useEffect(() => {
    setIntro(shouldPlayIntro());
    markIntroDone();
  }, []);
  const data: DeskData | null = useMemo(
    () =>
      intro === null
        ? null
        : { stops: stops.map((x) => ({ label: `${x.object} → ${lang === "en" ? x.scene.en.page : x.scene.page}`, href: x.scene.path })), intro, lang },
    [stops, intro, lang]
  );

  useEffect(() => {
    if (!on || !stage) return;
    const stopIndex = (el: EventTarget | null) => {
      const a = (el as HTMLElement | null)?.closest?.("a");
      if (!a || !a.closest("[data-shell-main]") || a.closest("[hidden]")) return -1;
      return stops.findIndex((x) => x.scene.path === a.getAttribute("href"));
    };
    const onFocusIn = (e: FocusEvent) => {
      const k = stopIndex(e.target);
      stage.command(k >= 0 ? { type: "focus", k } : { type: "blur" });
    };
    const onFocusOut = (e: FocusEvent) => {
      if (stopIndex(e.relatedTarget) < 0) stage.command({ type: "blur" });
    };
    const onClick = (e: MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      const k = stopIndex(e.target);
      if (k < 0) return;
      e.preventDefault();
      stage.command({ type: "enter", k });
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey || typingInto(e.target)) return;
      const dir = { ArrowDown: 1, ArrowRight: 1, PageDown: 1, ArrowUp: -1, ArrowLeft: -1, PageUp: -1 }[e.key];
      if (dir) {
        e.preventDefault();
        stage.command({ type: "step", dir });
      } else if (e.key === "Enter" && stopIndex(e.target) < 0 && !(e.target as HTMLElement).closest?.("a, button") && at > 0) {
        stage.command({ type: "enter", k: at - 1 });
      } else stage.command({ type: "skip-intro" });
    };
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    document.addEventListener("click", onClick, true);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [on, stage, stops, at]);

  const introPlaying = on && Boolean(st.intro);

  return (
    <>
      {data && <StageScene kind="desk" sceneKey="desk" data={data} />}
      {on &&
        createPortal(
          <div className={s.overlay}>
            <div className={s.vignette} aria-hidden="true" />
            <Grain />
            <div className={s.deskHero} aria-hidden="true" data-off={at !== 0 || undefined} data-intro={introPlaying || undefined}>
              <div className={s.deskKicker}>{t("WUHAN MEMORY · 暗房里的一张木桌", "WUHAN MEMORY · A WOODEN DESK IN A DARKROOM")}</div>
              <div className={s.deskName}>{t("武汉记忆", "Wuhan Memory")}</div>
              <p className={s.deskSub}>{t("用一场对话，冲洗出一份画在地图上的武汉行程。", "One conversation, developed into a Wuhan trip drawn on a map.")}</p>
              {introPlaying && <div className={s.deskSkip}>{t("点一下跳过", "Click to skip")}</div>}
            </div>
            {stops.map((x, k) => (
              <div key={x.scene.path} className={`${s.deskStop} ${k % 2 ? s.left : s.right}`} data-on={at === k + 1 || undefined} aria-hidden="true">
                <div className={s.deskKicker}>
                  {t("物件", "Object")} {pad2(k + 1)} · {x.object} → {t(x.scene.page, x.scene.en.page)}
                </div>
                <h2 className={s.deskTitle}>{x.title}</h2>
                <p className={s.deskText}>{x.text}</p>
                {/* 鼠标点的入口；键盘用普通版的卡片（不在 Tab 顺序里重复一遍） */}
                <a
                  href={x.scene.path}
                  tabIndex={-1}
                  className={s.deskGo}
                  onClick={(e) => {
                    e.preventDefault();
                    stage?.command({ type: "enter", k });
                  }}
                >
                  {x.action} →
                </a>
              </div>
            ))}
            <div className={`${s.pager} ${s.deskPager}`}>
              <button type="button" className={s.btn} aria-label={t("上一站", "Previous stop")} disabled={at <= 0} onClick={() => stage?.command({ type: "step", dir: -1 })}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 19V5M6 11l6-6 6 6" />
                </svg>
              </button>
              <div className={s.range} aria-hidden="true">
                <b>{pad2(at + 1)}</b> / {pad2(n)} · {VIEW_NAMES[lang][at]}
              </div>
              <button type="button" className={s.btn} aria-label={t("下一站", "Next stop")} disabled={at >= n - 1} onClick={() => stage?.command({ type: "step", dir: 1 })}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 5v14M6 13l6 6 6-6" />
                </svg>
              </button>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
