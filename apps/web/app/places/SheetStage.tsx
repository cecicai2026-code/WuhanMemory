"use client";

/**
 * 纸页幕的立体版（设计规范第 8.3 节、第 15 节第 4 条）：桌面和纸旁边的物件由场景画，
 * 信纸就是普通版的那张纸（真实的网页文字），立体模式下浮在桌面上，落下来、标题逐字打出、条目按行显影（CSS，places.module.css）。
 * 内容超过一屏时滚动页面，纸往上推。
 *
 * 键盘：左右方向键换主题，Esc 回到晾片；四个主题的索引是真正的链接。书只是鼠标的快捷方式，键盘用索引。
 */
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { StageScene, useStage, useStageState } from "@/components/stage/StageProvider";
import type { SheetData } from "@/lib/scene3d/data";
import { Grain, typingInto } from "@/components/stage/StageBits";
import s from "@/components/stage/stage.module.css";

export function SheetStage({ data }: { data: SheetData }) {
  const stage = useStage();
  const st = useStageState();
  const on = stage?.mode === "on" && st?.kind === "sheet";

  // 这一幕可以滚动页面（另外两幕是滚轮走片，不滚动）
  useEffect(() => {
    if (!on) return;
    document.documentElement.dataset.stageScroll = "on";
    return () => {
      delete document.documentElement.dataset.stageScroll;
    };
  }, [on]);

  // 告诉场景纸在屏幕上的左右边，贴纸、钢笔、书摆在纸两边的空白里
  useEffect(() => {
    if (!on || !stage) return;
    const send = () => {
      // 量纸外面那一栏（纸本身在播落下的动画，量出来是歪的）；Next 藏起来的上一个页面跳过
      const paper = [...document.querySelectorAll("[data-stage-paper]")].find((el) => !el.closest("[hidden]"));
      const col = paper?.parentElement;
      if (!col) return;
      const r = col.getBoundingClientRect();
      stage.command({ type: "layout", left: r.left, right: r.right });
    };
    send();
    window.addEventListener("resize", send);
    return () => window.removeEventListener("resize", send);
  }, [on, stage, data.topic]);

  useEffect(() => {
    if (!on || !stage) return;
    const k = data.topics.findIndex((t) => t.id === data.topic);
    const topicHref = (i: number) => `/places/${encodeURIComponent(data.id)}/${data.topics[(i + data.topics.length) % data.topics.length].id}`;
    const backHref = `/places/${encodeURIComponent(data.id)}`;
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey || typingInto(e.target)) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        stage.go(topicHref(k + (e.key === "ArrowRight" ? 1 : -1)), false);
      } else if (e.key === "Escape") stage.go(backHref);
    };
    // 左下角的"回到晾片"：落黑幕再走
    const onClick = (e: MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      const a = (e.target as HTMLElement).closest?.("a");
      if (a && a.getAttribute("href") === backHref && a.closest("[data-shell-bottom]")) {
        e.preventDefault();
        stage.go(backHref);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onClick, true);
    };
  }, [on, stage, data]);

  return (
    <>
      <StageScene kind="sheet" sceneKey="sheet" data={data} />
      {on &&
        createPortal(
          // 暗角和颗粒放在纸的下面（z-index 低于正文），不压暗纸上的字
          <div className={`${s.overlay} ${s.under}`} aria-hidden="true">
            <div className={s.vignette} />
            <Grain />
          </div>,
          document.body
        )}
    </>
  );
}
