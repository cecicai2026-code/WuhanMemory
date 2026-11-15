"use client";

/**
 * 晾片幕的立体版（设计规范第 8.2 节）：告诉场景显示晾片绳和显影盘，再在画布上面放网页元素：
 * 上方的序号、景点名、"区 · 类别"、暂停开放的章；左右两侧换景点的黄铜按钮；显影盘上方的提示；进入时的景点名和主题名。
 *
 * 换景点：场景先把照片滑到中间，停稳 350 毫秒后才改地址（/places/[id]），由服务器取新景点的资料，
 * 普通版的内容也跟着换。快速连按、滚轮连滚时只取最后停下的那一个。
 *
 * 键盘：Tab 停在普通版的四个主题链接上时，对应的主题卡抬起并出现黄铜框，回车推镜头后进入纸页；
 * 停在"上一个 / 下一个景点"上时，绳子上那张照片探出来。左右方向键换景点，Esc 回到胶卷。
 */
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { StageScene, useStage, useStageState } from "@/components/stage/StageProvider";
import type { LineData } from "@/lib/scene3d/data";
import { pad2 } from "@/lib/places";
import { Grain, typingInto, useSlideTitle } from "@/components/stage/StageBits";
import s from "@/components/stage/stage.module.css";

/** 普通版里的链接指向哪里：/places/<id>/<主题> 或 /places/<id> */
function linkTarget(el: EventTarget | null): { id: string; topic: string | null } | null {
  const a = (el as HTMLElement | null)?.closest?.("a");
  if (!a || !a.closest("[data-shell-main]")) return null;
  const m = /^\/places\/([^/?#]+)(?:\/([^/?#]+))?$/.exec(a.getAttribute("href") ?? "");
  return m ? { id: decodeURIComponent(m[1]), topic: m[2] ?? null } : null;
}

export function LineStage({ data }: { data: LineData }) {
  const stage = useStage();
  const st = useStageState();
  const on = stage?.mode === "on" && st?.kind === "line";
  const sel = on ? Number(st.sel) : -1;
  const entering = on && Boolean(st.entering);
  const cardK = on ? Number(st.card) : -1;
  const title = useSlideTitle(sel);
  const shownPrint = title.shown >= 0 ? data.prints[title.shown] : undefined;
  const current = data.prints.find((p) => p.id === data.sel);
  const n = data.prints.length;

  // 场景里换了景点：等照片滑到位、再停 200 毫秒（连点、连滚时只取最后一个），才改地址、取新景点的资料。
  // 换页面时主线程要忙几十毫秒，放在照片滑动的中间会看到卡一下，放在停稳以后就看不出来
  const selId = on ? (st.id as string | null) : null;
  const moving = on && Boolean(st.moving);
  useEffect(() => {
    if (!stage || !selId || selId === data.sel || entering || moving) return;
    const t = window.setTimeout(() => stage.go(`/places/${encodeURIComponent(selId)}`, false), 200);
    return () => window.clearTimeout(t);
  }, [stage, selId, data.sel, entering, moving]);

  // 键盘和普通版链接
  useEffect(() => {
    if (!on || !stage) return;
    const back = () => stage.go(`/places?at=${encodeURIComponent(data.sel)}`);
    const onFocusIn = (e: FocusEvent) => {
      const tg = linkTarget(e.target);
      if (tg?.topic && tg.id === data.sel) stage.command({ type: "focus-topic", id: tg.topic });
      else if (tg && !tg.topic) stage.command({ type: "focus-print", id: tg.id });
      else stage.command({ type: "blur" });
    };
    const onFocusOut = (e: FocusEvent) => {
      if (!linkTarget(e.relatedTarget)) stage.command({ type: "blur" });
    };
    const onClick = (e: MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      // 左下角的"回到胶卷"：落黑幕再走
      const a = (e.target as HTMLElement).closest?.("a");
      if (a && /^\/places\?at=/.test(a.getAttribute("href") ?? "")) {
        e.preventDefault();
        stage.go(a.getAttribute("href")!);
        return;
      }
      const tg = linkTarget(e.target);
      if (tg?.topic && tg.id === data.sel) {
        e.preventDefault();
        stage.command({ type: "enter-topic", id: tg.topic });
      } else if (tg && !tg.topic) {
        // 上一个、下一个景点：照片先滑过去，地址随后跟上
        e.preventDefault();
        stage.command({ type: "select", id: tg.id });
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey || typingInto(e.target)) return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        stage.command({ type: "step", dir: e.key === "ArrowRight" ? 1 : -1 });
      } else if (e.key === "Escape") back();
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
  }, [on, stage, data.sel]);

  const hoveredTopic = cardK >= 0 ? data.topics[cardK] : undefined;
  // 标题下面一行和暂停开放的章只对当前景点（地址里的那个）写；场景刚滑到别的照片、资料还没取到时先不写
  const showingCurrent = shownPrint?.id === data.sel;

  return (
    <>
      <StageScene kind="line" sceneKey="line" data={data} />
      {on &&
        createPortal(
          <div className={s.overlay}>
            <div className={s.vignette} aria-hidden="true" data-entering={entering || undefined} />
            <Grain />
            <div className={s.head} aria-hidden="true" data-entering={entering || undefined}>
              <div className={s.no}>{shownPrint ? `第 ${pad2(shownPrint.no)} 张 / ${pad2(n)}` : ""}</div>
              <div className={s.title}>
                <span className={title.className}>{shownPrint?.name}</span>
              </div>
              <div className={s.sub}>
                {showingCurrent ? data.sub : shownPrint?.district}
                {shownPrint?.credit && <span className={s.credit}>{shownPrint.credit}</span>}
              </div>
              {showingCurrent && current?.closed && <div className={s.closedStamp}>暂停开放</div>}
            </div>
            <button
              type="button"
              className={`${s.btn} ${s.prev} ${s.side}`}
              aria-label="上一个景点"
              disabled={sel <= 0}
              data-entering={entering || undefined}
              onClick={() => stage?.command({ type: "step", dir: -1 })}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M19 12H5M11 6l-6 6 6 6" />
              </svg>
            </button>
            <button
              type="button"
              className={`${s.btn} ${s.next} ${s.side}`}
              aria-label="下一个景点"
              disabled={sel >= n - 1}
              data-entering={entering || undefined}
              onClick={() => stage?.command({ type: "step", dir: 1 })}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
            {/* 主题卡抬起来时提示字隐去（样片的做法），免得压在卡上 */}
            <div className={s.hint} aria-hidden="true" data-entering={entering || hoveredTopic ? true : undefined}>
              显影盘 · 选一个主题
            </div>
            <div className={s.enter} aria-hidden="true" data-entering={entering || undefined}>
              <div className={s.enterName}>
                {current?.name}
                {hoveredTopic && ` · ${hoveredTopic.name}`}
              </div>
              <div className={s.enterSub}>进入纸页</div>
            </div>
            <div className={s.curtain} aria-hidden="true" data-entering={entering || undefined} />
          </div>,
          document.body
        )}
    </>
  );
}
