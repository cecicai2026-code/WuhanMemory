"use client";

/**
 * 胶卷幕的立体版（设计规范第 8.1 节）：告诉场景显示胶卷（StageScene），再在画布上面放网页元素：
 * 上方的格号和景点名、底部的黄铜按钮和刻度、暗角和颗粒、进入时的黑幕。
 *
 * 键盘和读屏软件用的是普通版的景点卡片（还在页面里，只是视觉上隐藏）：
 * Tab 停到某张卡片时，看片器滑到那一格，画框周围出现黄铜框；回车时镜头推近，再进入那个景点。
 * 方向键一格一格走，PageUp / PageDown 换组。立体版没打开时这里什么都不显示。
 */
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { StageScene, useStage, useStageState } from "@/components/stage/StageProvider";
import type { RollsData } from "@/lib/scene3d/data";
import { pad2 } from "@/lib/places";
import { makeT } from "@/lib/i18n";
import { Grain, typingInto, useSlideTitle } from "@/components/stage/StageBits";
import s from "@/components/stage/stage.module.css";

const G = 5;
/** /places/<id>，不带后面的主题 */
const PLACE_HREF = /^\/places\/([^/?#]+)$/;

function placeIdOf(el: EventTarget | null): string | null {
  const a = (el as HTMLElement | null)?.closest?.("a");
  if (!a || !a.closest("[data-shell-main]")) return null;
  const m = PLACE_HREF.exec(a.getAttribute("href") ?? "");
  return m ? decodeURIComponent(m[1]) : null;
}

export function RollsStage({ data, stageKey }: { data: RollsData; stageKey: string }) {
  const t = makeT(data.lang);
  const stage = useStage();
  const st = useStageState();
  const on = stage?.mode === "on" && st?.kind === "rolls";
  const sel = on ? Number(st.sel) : -1;
  const group = on ? Number(st.group) : 0;
  const groups = on ? Number(st.groups) : 1;
  const entering = on && Boolean(st.entering);
  const frame = sel >= 0 ? data.frames[sel] : undefined;

  const title = useSlideTitle(sel);
  const titleFrame = title.shown >= 0 ? data.frames[title.shown] : undefined;

  // 地址里记着停在哪一格（?at=），刷新或分享后停在同一格。停稳 400 毫秒再改，免得鼠标划过时一直改
  const lastAt = useRef<string | null>(null);
  useEffect(() => {
    if (!on || !frame || entering) return;
    const t = window.setTimeout(() => {
      if (lastAt.current === frame.id) return;
      lastAt.current = frame.id;
      const url = new URL(window.location.href);
      url.searchParams.set("at", frame.id);
      window.history.replaceState(window.history.state, "", url);
    }, 400);
    return () => window.clearTimeout(t);
  }, [on, frame, entering]);

  // 键盘：焦点停在某张卡片上时让场景跟过去；回车先推镜头再进入
  useEffect(() => {
    if (!on || !stage) return;
    const onFocusIn = (e: FocusEvent) => {
      const id = placeIdOf(e.target);
      if (id) stage.command({ type: "focus", id });
      else stage.command({ type: "blur" });
    };
    const onFocusOut = (e: FocusEvent) => {
      if (!placeIdOf(e.relatedTarget)) stage.command({ type: "blur" });
    };
    const onClick = (e: MouseEvent) => {
      const id = placeIdOf(e.target);
      if (!id || e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      stage.command({ type: "enter", id });
    };
    // Next 会把上一个页面藏在 hidden 的容器里留着，跳过那些
    const links = () => [...document.querySelectorAll<HTMLAnchorElement>("[data-shell-main] a")].filter((a) => placeIdOf(a) && !a.closest("[hidden]"));
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey) return;
      const t = e.target as HTMLElement;
      if (typingInto(t)) return;
      const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      const inList = placeIdOf(t) !== null;
      if (dir) {
        e.preventDefault();
        if (inList) {
          // 焦点在卡片上：把焦点移到下一张卡片，场景跟着走
          const ls = links();
          const i = ls.findIndex((a) => a === t.closest("a"));
          ls[Math.max(0, Math.min(ls.length - 1, i + dir))]?.focus();
        } else stage.command({ type: "step", dir });
      } else if (e.key === "PageDown" || e.key === "PageUp") {
        e.preventDefault();
        stage.command({ type: "page", dir: e.key === "PageDown" ? 1 : -1 });
      } else if (e.key === "Enter" && !inList && (t === document.body || !t.closest("a, button"))) {
        stage.command({ type: "enter" });
      }
    };
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    document.addEventListener("click", onClick, true);
    document.addEventListener("keydown", onKey);
    // 打开立体版时焦点已经在某张卡片上：让场景跟过去
    const cur = placeIdOf(document.activeElement);
    if (cur) stage.command({ type: "focus", id: cur });
    return () => {
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [on, stage]);

  const a = group * G,
    b = Math.min(data.frames.length, a + G);

  return (
    <>
      <StageScene kind="rolls" sceneKey={stageKey} data={data} />
      {/* 放到 <body> 下面：页面正文在立体模式下是隐藏的，放在正文里会跟着看不见 */}
      {on &&
        createPortal(
        <div className={s.overlay}>
          <div className={s.vignette} aria-hidden="true" data-entering={entering || undefined} />
          <Grain />
          <div className={s.head} aria-hidden="true" data-entering={entering || undefined}>
            <div className={s.no}>{titleFrame ? t(`第 ${pad2(titleFrame.no)} 格 / ${pad2(data.total)}`, `Frame ${pad2(titleFrame.no)} / ${pad2(data.total)}`) : ""}</div>
            <div className={s.title}>
              <span className={title.className}>{titleFrame?.name}</span>
            </div>
            {titleFrame && (
              <div className={s.sub}>
                {[titleFrame.district, titleFrame.closed && t("暂停开放", "Temporarily closed"), titleFrame.counts].filter(Boolean).join(" · ")}
                {titleFrame.credit && <span className={s.credit}>{titleFrame.credit}</span>}
              </div>
            )}
          </div>
          <div className={s.pager} data-entering={entering || undefined}>
            <button type="button" className={`${s.btn} ${s.prev}`} aria-label={t("上一组景点", "Previous places")} disabled={group === 0} onClick={() => stage?.command({ type: "page", dir: -1 })}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M19 12H5M11 6l-6 6 6 6" />
              </svg>
            </button>
            <div className={s.scale} aria-hidden="true">
              <div className={s.range}>
                <b>
                  {pad2(a + 1)} — {pad2(b)}
                </b>{" "}
                / {pad2(data.frames.length)}
              </div>
              <div className={s.ticks}>
                {data.frames.map((f, k) => (
                  <i key={f.id} className={k === sel ? s.tickSel : k >= a && k < b ? s.tickGroup : undefined} />
                ))}
              </div>
            </div>
            <button type="button" className={`${s.btn} ${s.next}`} aria-label={t("下一组景点", "Next places")} disabled={group >= groups - 1} onClick={() => stage?.command({ type: "page", dir: 1 })}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          </div>
          <div className={s.enter} aria-hidden="true" data-entering={entering || undefined}>
            <div className={s.enterName}>{frame?.name}</div>
            <div className={s.enterSub}>{t("进入晾片", "To the drying line")}</div>
          </div>
          <div className={s.curtain} aria-hidden="true" data-entering={entering || undefined} />
        </div>,
          document.body
        )}
    </>
  );
}
