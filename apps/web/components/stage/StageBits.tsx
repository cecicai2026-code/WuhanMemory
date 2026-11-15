"use client";

/** 地点档案几幕的立体版共用的网页小部件：颗粒、换标题时的滑动 */
import { useEffect, useRef, useState } from "react";
import s from "./stage.module.css";

/** 全页一层细颗粒（设计规范 3.2、G7）。降级时由 CSS 关掉 */
export function Grain() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const g = c?.getContext("2d");
    if (!c || !g) return;
    const d = g.createImageData(256, 256);
    for (let i = 0; i < d.data.length; i += 4) {
      const v = Math.random() * 255;
      d.data[i] = d.data[i + 1] = d.data[i + 2] = v;
      d.data[i + 3] = 255;
    }
    g.putImageData(d, 0, 0);
  }, []);
  return <canvas ref={ref} className={s.grain} width={256} height={256} aria-hidden="true" />;
}

/**
 * 标题换的时候先滑出去再滑进来（样片的做法）。返回现在显示第几个，以及加在 <span> 上的 class。
 */
export function useSlideTitle(sel: number): { shown: number; className: string | undefined } {
  const [state, setState] = useState<{ i: number; phase: "in" | "out" | "" }>({ i: -1, phase: "" });
  useEffect(() => {
    if (sel < 0 || sel === state.i) return;
    if (state.i < 0) {
      setState({ i: sel, phase: "" });
      return;
    }
    setState((p) => ({ ...p, phase: "out" }));
    const t1 = window.setTimeout(() => setState({ i: sel, phase: "in" }), 180);
    const t2 = window.setTimeout(() => setState({ i: sel, phase: "" }), 220);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel]);
  return { shown: state.i, className: state.phase ? s[state.phase] : undefined };
}

/** 是不是在输入框、菜单、对话框里（这时方向键等留给它们） */
export function typingInto(t: EventTarget | null): boolean {
  return !!(t as HTMLElement | null)?.closest?.("input, textarea, select, [role=dialog], [aria-expanded=true]");
}
