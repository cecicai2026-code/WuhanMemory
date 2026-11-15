"use client";

import { useEffect, useMemo, useState } from "react";
import type { MapRoute } from "@wuhanmemory/map-core";
import type { ItineraryVersion, PlanningRound, PoiSummary, Route } from "@wuhanmemory/shared";
import { NoteButton } from "@/components/ui";
import { useT } from "@/components/i18n/LangProvider";
import { itineraryPins, itineraryRoutes, type PinOverride } from "@/lib/itinerary-map";
import { getRound, getVersion } from "@/lib/planning-client";
import { ChatPaper, type PlanResult } from "./ChatPaper";
import { ItineraryCards } from "./ItineraryCards";
import { MapPanel } from "./MapPanel";
import { PlanCompare } from "./PlanCompare";
import { usePlannerState } from "./PlannerState";
import { RouteFinder } from "./RouteFinder";
import s from "./map.module.css";

type Tab = "chat" | "plan";

/**
 * 地图工作台（设计规范 9.1）：左边对话纸（ChatPaper），中间灯箱里的地图（MapPanel），右边行程卡（ItineraryCards）。
 *
 * 板块 5B：一次规划是一轮三份方案。右边先是方案对比卡（切换看哪一份），下面是选中那份的行程卡；
 * 地图上画选中的那一份。板块 5 存的旧回复只有一个版本，照旧显示。
 *
 * 有行程时，地图上只放这一天的景点（图钉名字前加上顺序），画出这一天每段交通的折线；
 * 多天的行程用行程卡上的"地图上看 第 N 天"切换。没通过校验的行程不画。
 *
 * 电脑上三栏并排。手机上地图在上，对话和行程收在底部面板里，用两个纸签切换，可以收起。
 */
export function Workbench({ pois, poisError }: { pois: PoiSummary[]; poisError: string | null }) {
  const { setValidation } = usePlannerState();
  const t = useT();
  const [tab, setTab] = useState<Tab>("chat");
  const [open, setOpen] = useState(true);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [round, setRound] = useState<PlanningRound | null>(null);
  const [picked, setPicked] = useState(0);
  const [version, setVersion] = useState<ItineraryVersion | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);
  // 地图上看哪一天；"all" 是全部天，每天一种颜色
  const [shownDay, setShownDay] = useState<number | "all" | null>(null);
  // "两点之间怎么走"（板块 3，临时）选中的那一种交通方式
  const [shownRoute, setShownRoute] = useState<Route | null>(null);

  function show(v: ItineraryVersion) {
    setVersion(v);
    setShownDay(v.days[0]?.dayNumber ?? null);
    setShownRoute(null);
    setValidation(v.validation.status, v.planner.providerLabel);
  }

  useEffect(() => {
    if (!result) return;
    let closed = false;
    setVersionLoading(true);
    setVersionError(null);
    async function load(r: PlanResult): Promise<void> {
      if ("versionId" in r) {
        setRound(null);
        const v = await getVersion(r.versionId);
        if (!closed) show(v);
        return;
      }
      const got = await getRound(r.roundId);
      if (closed) return;
      setRound(got);
      setPicked(0);
      if (got.versions.length) {
        show(got.versions[0]);
        return;
      }
      // 一份都没展示：取第一份存下的版本，只显示它的问题清单（和板块 5 一样，不画时间线和地图）
      const first = got.plans.find((p) => p.versionId);
      if (first?.versionId) {
        const v = await getVersion(first.versionId);
        if (!closed) show(v);
      } else {
        setVersion(null);
        setValidation(null);
      }
    }
    load(result)
      .then(() => {
        // 手机上：排好了就切到行程
        if (!closed) setTab("plan");
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
  }, [result, setValidation]);

  function pick(index: number) {
    if (!round?.versions[index]) return;
    setPicked(index);
    show(round.versions[index]);
  }

  const routes = useMemo<MapRoute[]>(() => {
    const days = itineraryRoutes(version, shownDay);
    if (days.length) return days;
    return shownRoute ? [{ id: shownRoute.mode, dayNumber: null, lines: [{ mode: shownRoute.mode, path: shownRoute.polyline }] }] : [];
  }, [version, shownDay, shownRoute]);

  const pins = useMemo<PinOverride[] | null>(() => itineraryPins(version, shownDay), [version, shownDay]);

  function choose(next: Tab) {
    setTab(next);
    setOpen(true);
  }

  function reset() {
    setResult(null);
    setRound(null);
    setPicked(0);
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
          {t("对话", "Chat")}
        </NoteButton>
        <NoteButton pressed={open && tab === "plan"} onClick={() => choose("plan")}>
          {t("行程", "Trip")}
        </NoteButton>
        <button className={s.fold} type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? t("收起 ↓", "Collapse ↓") : t("展开 ↑", "Expand ↑")}
        </button>
      </div>

      <section className={`${s.col} ${s.chatCol}`} aria-label={t("对话", "Chat")}>
        <ChatPaper onResult={setResult} onReset={reset} />
      </section>

      <section className={`${s.col} ${s.mapCol}`} aria-label={t("地图", "Map")}>
        <MapPanel pois={pois} poisError={poisError} routes={routes} pins={pins} />
      </section>

      <section className={`${s.col} ${s.planCol}`} aria-label={t("行程", "Trip")}>
        <div className={s.cards}>
          {round && !versionLoading && <PlanCompare round={round} picked={picked} onPick={pick} />}
          <ItineraryCards
            version={version}
            loading={versionLoading}
            error={versionError}
            shownDay={shownDay}
            onShowDay={setShownDay}
            shareable
          />
          <RouteFinder pois={pois} shown={shownRoute?.mode ?? null} onShow={setShownRoute} />
        </div>
      </section>
    </div>
  );
}
