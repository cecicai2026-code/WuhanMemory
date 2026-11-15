"use client";

import { useMemo, useState } from "react";
import type { MapRoute } from "@wuhanmemory/map-core";
import type { PoiSummary, Route } from "@wuhanmemory/shared";
import { BrassButton, LineInput, NoteButton, Paper, PaperMark, PaperTitle, PencilNote, Rule } from "@/components/ui";
import { MapPanel } from "./MapPanel";
import { RouteFinder } from "./RouteFinder";
import s from "./map.module.css";

type Tab = "chat" | "plan";

/**
 * 地图工作台的布局（设计规范 9.1）。板块 1A 只做布局：
 * 对话在板块 5 接入，行程卡在板块 5 有数据后才出现。地图（板块 3）在 MapPanel 里。
 * 所以这里没有任何示例对话、示例行程或示例数字。
 *
 * 电脑上三栏并排。手机上地图在上，对话和行程收在底部面板里，
 * 用两个纸签切换，可以收起。tab 和 open 两个状态只在手机上起作用。
 */
export function Workbench({ pois, poisError }: { pois: PoiSummary[]; poisError: string | null }) {
  const [tab, setTab] = useState<Tab>("chat");
  const [open, setOpen] = useState(true);
  // "两点之间怎么走"选中的那一种交通方式，画在地图上
  const [shownRoute, setShownRoute] = useState<Route | null>(null);
  const routes = useMemo<MapRoute[]>(
    () => (shownRoute ? [{ id: shownRoute.mode, dayNumber: null, lines: [{ mode: shownRoute.mode, path: shownRoute.polyline }] }] : []),
    [shownRoute],
  );

  function choose(next: Tab) {
    setTab(next);
    setOpen(true);
  }

  return (
    <div className={s.bench} data-tab={tab} data-open={open}>
      {/* 只在手机上显示：切换底部面板 */}
      <div className={s.tabs}>
        <NoteButton pressed={open && tab === "chat"} onClick={() => choose("chat")}>
          对话
        </NoteButton>
        <NoteButton pressed={open && tab === "plan"} onClick={() => choose("plan")}>
          行程
        </NoteButton>
        <button className={s.fold} type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "收起 ↓" : "展开 ↑"}
        </button>
      </div>

      <section className={`${s.col} ${s.chatCol}`} aria-label="对话">
        <Paper className={s.chat}>
          <div className={s.log}>
            <PaperMark>打字纸 · 对话</PaperMark>
            <PaperTitle>还没有对话</PaperTitle>
            <Rule />
            <p>在这里用日常的话说你想怎么玩，例如几天、想看什么、走路多不多。回复会打在这张纸上。</p>
          </div>
          <form className={s.ask} onSubmit={(e) => e.preventDefault()}>
            <LineInput id="ask" label="想怎么玩" placeholder="对话还没有接入" disabled />
            <div className={s.askRow}>
              <PencilNote>板块 5 接入</PencilNote>
              <BrassButton type="submit" disabled>
                发送
              </BrassButton>
            </div>
          </form>
        </Paper>
      </section>

      <section className={`${s.col} ${s.mapCol}`} aria-label="地图">
        <MapPanel pois={pois} poisError={poisError} routes={routes} />
      </section>

      <section className={`${s.col} ${s.planCol}`} aria-label="行程">
        <div className={s.cards}>
          <RouteFinder pois={pois} shown={shownRoute?.mode ?? null} onShow={setShownRoute} />
          <Paper kind="card" tilt={1}>
            <PaperMark>索引卡 · 行程</PaperMark>
            <PaperTitle level={3}>还没有行程</PaperTitle>
            <p>生成行程后，这里每天一张卡。</p>
            <ul className={s.what}>
              <li>时间线</li>
              <li>每段交通方式和时间</li>
              <li>支付和预约提示</li>
              <li>右上角是校验结果的印章</li>
            </ul>
            <PencilNote>板块 5 接入</PencilNote>
          </Paper>
        </div>
      </section>
    </div>
  );
}
