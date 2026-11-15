"use client";

import { useEffect, useMemo, useState } from "react";
import type { MapRoute } from "@wuhanmemory/map-core";
import type { ItineraryVersion, PoiSummary, Route } from "@wuhanmemory/shared";
import { NoteButton } from "@/components/ui";
import { getVersion } from "@/lib/planning-client";
import { ChatPaper } from "./ChatPaper";
import { ItineraryCards } from "./ItineraryCards";
import { MapPanel, type PinOverride } from "./MapPanel";
import { usePlannerState } from "./PlannerState";
import { RouteFinder } from "./RouteFinder";
import s from "./map.module.css";

type Tab = "chat" | "plan";

/**
 * 地图工作台（设计规范 9.1）：左边对话纸（ChatPaper），中间灯箱里的地图（MapPanel），右边行程卡（ItineraryCards）。
 *
 * 有行程时，地图上只放这一天的景点（图钉名字前加上顺序），画出这一天每段交通的折线；
 * 多天的行程用行程卡上的"地图上看 第 N 天"切换。没通过校验的行程不画。
 *
 * 电脑上三栏并排。手机上地图在上，对话和行程收在底部面板里，用两个纸签切换，可以收起。
 */
export function Workbench({ pois, poisError }: { pois: PoiSummary[]; poisError: string | null }) {
  const { setValidation } = usePlannerState();
  const [tab, setTab] = useState<Tab>("chat");
  const [open, setOpen] = useState(true);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [version, setVersion] = useState<ItineraryVersion | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [shownDay, setShownDay] = useState<number | null>(null);
  // "两点之间怎么走"（板块 3，临时）选中的那一种交通方式
  const [shownRoute, setShownRoute] = useState<Route | null>(null);

  useEffect(() => {
    if (!versionId) return;
    let closed = false;
    setVersionLoading(true);
    setVersionError(null);
    getVersion(versionId)
      .then((v) => {
        if (closed) return;
        setVersion(v);
        setShownDay(v.days[0]?.dayNumber ?? null);
        setShownRoute(null);
        setValidation(v.validation.status, v.planner.providerLabel);
        // 手机上：排好了就切到行程
        setTab("plan");
      })
      .catch((err: unknown) => {
        if (!closed) setVersionError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!closed) setVersionLoading(false);
      });
    return () => {
      closed = true;
    };
  }, [versionId, setValidation]);

  const shown = version && version.validation.status !== "failed" ? version.days.find((d) => d.dayNumber === shownDay) : undefined;

  const routes = useMemo<MapRoute[]>(() => {
    if (shown) {
      return [
        {
          id: `day-${shown.dayNumber}`,
          dayNumber: shown.dayNumber,
          lines: shown.legs.filter((l) => l.route.polyline.length > 1).map((l) => ({ mode: l.route.mode, path: l.route.polyline })),
        },
      ];
    }
    return shownRoute ? [{ id: shownRoute.mode, dayNumber: null, lines: [{ mode: shownRoute.mode, path: shownRoute.polyline }] }] : [];
  }, [shown, shownRoute]);

  const pins = useMemo<PinOverride[] | null>(
    () => (shown ? shown.stops.map((st, i) => ({ id: st.poiId, name: `${i + 1} · ${st.name}`, location: st.location })) : null),
    [shown],
  );

  function choose(next: Tab) {
    setTab(next);
    setOpen(true);
  }

  function reset() {
    setVersionId(null);
    setVersion(null);
    setVersionError(null);
    setShownDay(null);
    setValidation(null);
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
        <ChatPaper onVersion={setVersionId} onReset={reset} />
      </section>

      <section className={`${s.col} ${s.mapCol}`} aria-label="地图">
        <MapPanel pois={pois} poisError={poisError} routes={routes} pins={pins} />
      </section>

      <section className={`${s.col} ${s.planCol}`} aria-label="行程">
        <div className={s.cards}>
          <ItineraryCards
            version={version}
            loading={versionLoading}
            error={versionError}
            shownDay={shownDay}
            onShowDay={setShownDay}
          />
          <RouteFinder pois={pois} shown={shownRoute?.mode ?? null} onShow={setShownRoute} />
        </div>
      </section>
    </div>
  );
}
