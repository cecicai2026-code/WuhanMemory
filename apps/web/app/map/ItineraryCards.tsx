"use client";

import { useEffect, useState, type ReactNode } from "react";
import type {
  DayOrder,
  FactStatus,
  ItineraryDay,
  ItineraryLeg,
  ItineraryStop,
  ItineraryVersion,
  PoiFact,
  ShareLink,
  ValidationIssue,
} from "@wuhanmemory/shared";
import { NoteButton, Paper, PaperMark, PaperTitle, PencilNote, Rule, Soft, Stamp, TextLink } from "@/components/ui";
import { ShareControls } from "@/components/trip/ShareControls";
import { getVersionShare } from "@/lib/planning-client";
import { formatOpeningHours, formatPayment, formatReservation, formatTicket } from "@/lib/format-poi";
import { DAY_COLOR_NAMES, dayColor } from "./day-colors";
import { useLang } from "@/components/i18n/LangProvider";
import { makeT, modelName, type T } from "@/lib/i18n";
import s from "./map.module.css";

const WEEKDAY = {
  zh: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"],
  en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
};
const MODE_TEXT = { walk: { zh: "步行", en: "Walk" }, transit: { zh: "公交地铁", en: "Bus/metro" }, drive: { zh: "打车", en: "Taxi" } } as const;
const EMPHASIS_TEXT = {
  classic: { zh: "经典必去", en: "The classics" },
  relaxed: { zh: "轻松少走路", en: "Easy, less walking" },
  culture: { zh: "深度文化", en: "Deep culture" },
} as const;

/** 当前语言的 t：这个文件里的组件都用它 */
function useTr(): T {
  return makeT(useLang());
}
/** 这几种问题说的是两站之间的交通，标在交通那一行，不标在景点上 */
const LEG_CODES = new Set(["overlap", "transport-too-short", "transport-tight", "route-unknown", "route-stale"]);
/** 这两种问题在每条资料旁边已经用"待确认""待补充"标出来了，景点下面不再重复 */
const FACT_CODES = new Set(["data-pending", "data-missing"]);

function dayLabel(day: ItineraryDay, t: T): string {
  if (!day.date) return t(`第 ${day.dayNumber} 天 · 日期未定`, `Day ${day.dayNumber} · date not set`);
  const d = new Date(`${day.date}T00:00:00`);
  const md = day.date.slice(5).replace("-", ".");
  return t(`第 ${day.dayNumber} 天 · ${md} ${WEEKDAY.zh[d.getDay()]}`, `Day ${day.dayNumber} · ${WEEKDAY.en[d.getDay()]} ${md}`);
}

function FactTag({ status }: { status: FactStatus }) {
  const t = useTr();
  if (status === "verified") return null;
  const text = { pending: t("待确认", "to confirm"), missing: t("待补充", "to fill in"), expired: t("已过期", "expired") }[status];
  return (
    <span className={s.factTag} data-status={status}>
      {text}
    </span>
  );
}

function Fact<V>({ label, fact, format }: { label: string; fact: PoiFact<V>; format: (v: V, t: T) => string }) {
  const t = useTr();
  const text = fact.value !== null && fact.value !== undefined ? format(fact.value, t) : t("没有资料", "No info");
  return (
    <>
      <dt>{label}</dt>
      <dd>
        <span className={s.factText}>{text}</span> <FactTag status={fact.status} />
      </dd>
    </>
  );
}

function Issues({ issues }: { issues: ValidationIssue[] }) {
  const t = useTr();
  if (!issues.length) return null;
  return (
    <ul className={s.issues}>
      {issues.map((i, n) => (
        <li key={n} data-level={i.level}>
          <span aria-hidden="true">{i.level === "error" ? "✕" : "!"}</span>
          <span className="sr-only">{i.level === "error" ? t("错误：", "Error: ") : t("警告：", "Warning: ")}</span>
          {i.message}
        </li>
      ))}
    </ul>
  );
}

function Leg({ leg, issues }: { leg: ItineraryLeg | undefined; issues: ValidationIssue[] }) {
  const t = useTr();
  const r = leg?.route;
  const ok = r && r.status === "ok" && r.durationMinutes != null;
  return (
    <li className={s.leg}>
      <p>
        <span aria-hidden="true">↓ </span>
        {ok ? (
          <>
            <strong>{t(`${MODE_TEXT[r.mode].zh} ${r.durationMinutes} 分钟`, `${MODE_TEXT[r.mode].en} ${r.durationMinutes} min`)}</strong>
            {r.distanceMeters != null && t(` · ${(r.distanceMeters / 1000).toFixed(1)} 公里`, ` · ${(r.distanceMeters / 1000).toFixed(1)} km`)}
            {r.cost?.amountCny != null && r.cost.kind !== "free" && t(` · 约 ${r.cost.amountCny} 元`, ` · about ¥${r.cost.amountCny}`)}
            {r.summary && ` · ${r.summary}`}
          </>
        ) : (
          <strong>{t("交通没查到", "No route found")}</strong>
        )}
      </p>
      {leg && (
        <p className={s.legMeta}>
          {leg.choice}
          {r?.checkedAt && t(` · 高德，${r.checkedAt.slice(5, 10).replace("-", ".")} 查询`, ` · AMap, looked up ${r.checkedAt.slice(5, 10).replace("-", ".")}`)}
          {r?.cache === "stale" && t(" · 缓存已过期", " · cached result expired")}
        </p>
      )}
      <Issues issues={issues} />
    </li>
  );
}

function Stop({ stop, issues }: { stop: ItineraryStop; issues: ValidationIssue[] }) {
  const t = useTr();
  const f = stop.facts;
  return (
    <li className={s.stop}>
      <p className={s.stopTime}>
        {stop.arrive ? `${stop.arrive}–${stop.leave}` : t("没排出时间", "No time set")}
      </p>
      <p className={s.stopName}>
        <TextLink href={`/places/${stop.poiId}`} onPaper>
          {stop.name}
        </TextLink>{" "}
        <Soft>{stop.district}</Soft>
      </p>
      {stop.reason && <p className={s.stopReason}>{stop.reason}</p>}
      <dl className={s.facts}>
        <Fact label={t("开放", "Hours")} fact={f.openingHours} format={formatOpeningHours} />
        <Fact label={t("预约", "Booking")} fact={f.reservation} format={formatReservation} />
        <Fact label={t("门票", "Tickets")} fact={f.ticket} format={formatTicket} />
        <Fact label={t("支付", "Payment")} fact={f.payment} format={formatPayment} />
      </dl>
      <Issues issues={issues} />
    </li>
  );
}

/**
 * 每天一张的卡片放平，不歪：卡片常有两三千像素高，歪 1 度时上下两头会横着偏出二十多像素，
 * 左边的字被右栏的滚动框裁掉（2026-11-15 Cecilia 反馈字贴边、被切）。短的总卡照旧歪。
 */
/** ADR 0010：这一天的顺序是不是程序按真实交通时间重排过 */
function OrderNote({ order }: { order: DayOrder | undefined }) {
  const t = useTr();
  if (!order) return null;
  const before = order.modelTransportMinutes;
  const after = order.transportMinutes;
  if (order.changed && before != null && after != null) {
    return (
      <p className={s.routeMeta}>
        {t(
          `顺序由程序按真实交通时间重排：路上 ${after} 分钟，模型原来的顺序要 ${before} 分钟（少 ${before - after} 分钟）。`,
          `Order rearranged by the program using real travel times: ${after} min on the road, versus ${before} min in the model's order (${before - after} min less).`
        )}
      </p>
    );
  }
  if (order.reason === "already-shortest") {
    return <p className={s.routeMeta}>{t("程序比较过所有顺序，模型的顺序已经是路上最省的。", "The program checked every order; the model's order already has the least travel time.")}</p>;
  }
  if (order.reason === "more-errors") {
    return <p className={s.routeMeta}>{t("有更省路的顺序，但会多出校验错误，所以保留模型的顺序。", "Shorter orders exist but would add check errors, so the model's order is kept.")}</p>;
  }
  return null;
}

function DayCard({ day, issues, order }: { day: ItineraryDay; issues: ValidationIssue[]; order?: DayOrder }) {
  const t = useTr();
  const mine = issues.filter((i) => i.dayNumber === day.dayNumber);
  const dayWide = mine.filter((i) => !i.poiId);
  const items: ReactNode[] = [];
  day.stops.forEach((stop, idx) => {
    if (idx > 0) {
      const prev = day.stops[idx - 1];
      const leg = day.legs.find((l) => l.fromPoiId === prev.poiId && l.toPoiId === stop.poiId);
      items.push(
        <Leg key={`leg-${idx}`} leg={leg} issues={mine.filter((i) => i.poiId === stop.poiId && LEG_CODES.has(i.code))} />,
      );
    }
    items.push(
      <Stop
        key={`stop-${idx}`}
        stop={stop}
        issues={mine.filter((i) => i.poiId === stop.poiId && !LEG_CODES.has(i.code) && !FACT_CODES.has(i.code))}
      />,
    );
  });
  const hasWarning = mine.length > 0;
  return (
    <Paper kind="card" className={s.sheet} as="article" aria-label={dayLabel(day, t)}>
      <div className={s.cardHead}>
        <PaperMark>{dayLabel(day, t)}</PaperMark>
        <Stamp status={hasWarning ? "pending" : "verified"}>{hasWarning ? t("有警告", "Warnings") : t("通过", "Passed")}</Stamp>
      </div>
      <PaperTitle level={3}>{day.theme || t(`第 ${day.dayNumber} 天`, `Day ${day.dayNumber}`)}</PaperTitle>
      <OrderNote order={order} />
      <Issues issues={dayWide} />
      <ol className={s.timeline}>{items}</ol>
    </Paper>
  );
}

/** 地图工作台上的分享按钮：先查这个版本有没有分享链接，再显示生成或复制、撤回 */
function MapShare({ versionId }: { versionId: string }) {
  const t = useTr();
  const [state, setState] = useState<{ kind: "loading" } | { kind: "ready"; link: ShareLink | null } | { kind: "error"; message: string }>({
    kind: "loading",
  });
  useEffect(() => {
    let closed = false;
    setState({ kind: "loading" });
    getVersionShare(versionId)
      .then((link) => !closed && setState({ kind: "ready", link }))
      .catch((err: unknown) => !closed && setState({ kind: "error", message: err instanceof Error ? err.message : String(err) }));
    return () => {
      closed = true;
    };
  }, [versionId]);
  if (state.kind === "loading") return <Soft>{t("正在查分享链接……", "Checking for a share link…")}</Soft>;
  if (state.kind === "error")
    return (
      <Soft>
        {t("分享链接查不到：", "Couldn't check the share link: ")}
        {state.message}
      </Soft>
    );
  return <ShareControls key={versionId} versionId={versionId} failed={false} initial={state.link} />;
}

interface Props {
  version: ItineraryVersion | null;
  loading: boolean;
  error: string | null;
  shownDay: number | "all" | null;
  onShowDay: (day: number | "all") => void;
  /** 地图工作台上给 true：总卡上放分享按钮。分享页和我的行程不给（它们自己有） */
  shareable?: boolean;
}

/**
 * 右边的索引卡：行程（设计规范 9.1）。
 * 第一张是总卡：校验结果的印章、用的模型、按默认补上的设置、每一条错误和警告。
 * 没通过校验的行程只显示问题清单，不显示时间线，地图上也不画（2026-11-15 Cecilia 确认）。
 * 其余每天一张：时间线、每段交通（高德查的真实时间）、预约和支付提示（景点库里的资料，旁边标着待确认、待补充）。
 */
export function ItineraryCards({ version, loading, error, shownDay, onShowDay, shareable = false }: Props) {
  const lang = useLang();
  const t = makeT(lang);
  if (loading) {
    return (
      <Paper kind="card" className={s.sheet} tilt={1}>
        <PaperMark>{t("索引卡 · 行程", "Index card · trip")}</PaperMark>
        <p>{t("正在取行程……", "Fetching the trip…")}</p>
      </Paper>
    );
  }
  if (error) {
    return (
      <Paper kind="card" className={s.sheet} tilt={1}>
        <PaperMark>{t("索引卡 · 行程", "Index card · trip")}</PaperMark>
        <p className={s.routeError} role="alert">
          {t("没取到行程：", "Couldn't fetch the trip: ")}
          {error}
        </p>
      </Paper>
    );
  }
  if (!version) {
    return (
      <Paper kind="card" className={s.sheet} tilt={1}>
        <PaperMark>{t("索引卡 · 行程", "Index card · trip")}</PaperMark>
        <PaperTitle level={3}>{t("还没有行程", "No trip yet")}</PaperTitle>
        <p>
          {t(
            "在左边的打字纸上说想怎么玩。排好、校验过的行程会出现在这里，每天一张卡，地图上同时画出路线。",
            "Say what kind of trip you want on the typing paper on the left. Once a trip is planned and checked it appears here, one card per day, with the routes drawn on the map."
          )}
        </p>
      </Paper>
    );
  }

  const v = version;
  const report = v.validation;
  const failed = report.status === "failed";
  const errors = report.issues.filter((i) => i.level === "error");
  const warnings = report.issues.filter((i) => i.level === "warning");
  const stamp =
    report.status === "passed" ? (
      <Stamp status="verified">{t("校验通过", "Checks passed")}</Stamp>
    ) : report.status === "warning" ? (
      <Stamp status="pending">{t("有警告", "Warnings")}</Stamp>
    ) : (
      <Stamp status="expired">{t("未通过", "Failed")}</Stamp>
    );
  const planner = v.planner;

  return (
    <>
      <Paper kind="card" className={s.sheet} tilt={-1} as="section" aria-label={t("行程总卡", "Trip summary card")}>
        <div className={s.cardHead}>
          <PaperMark>
            {v.emphasis ? `${t(EMPHASIS_TEXT[v.emphasis].zh, EMPHASIS_TEXT[v.emphasis].en)} · ` : t("行程 · ", "Trip · ")}
            {t(`第 ${v.versionNumber} 版`, `version ${v.versionNumber}`)}
          </PaperMark>
          {stamp}
        </div>
        <PaperTitle level={3}>{failed ? t("这份行程没通过校验", "This trip didn't pass the checks") : v.title}</PaperTitle>
        <p className={s.routeMeta}>
          {modelName(planner.providerLabel, lang)}
          {planner.model ? ` · ${planner.model}` : ""}
          {planner.rounds === 2
            ? t(` · 第一版有 ${planner.firstRoundErrors} 处错误，修正过一次`, ` · first draft had ${planner.firstRoundErrors} errors, fixed once`)
            : t(" · 一次生成", " · generated in one go")}
        </p>
        {failed && (
          <p>
            {t(
              `修正一次后仍有 ${errors.length} 处错误，所以不展示时间线，地图上也不画。可以换个说法或调整要求再发一次。`,
              `After one round of fixes there are still ${errors.length} errors, so no timeline is shown and nothing is drawn on the map. Try rewording or changing your request and send it again.`
            )}
          </p>
        )}
        {v.defaultsUsed.length > 0 && (
          <ul className={s.defaults}>
            {v.defaultsUsed.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        )}
        {errors.length > 0 && (
          <>
            <Rule dashed />
            <p className={s.issuesHead}>{t(`错误 ${errors.length} 条`, `${errors.length} errors`)}</p>
            <Issues issues={errors} />
          </>
        )}
        {warnings.length > 0 && (
          <details className={s.warnings} open={failed || warnings.length <= 4}>
            <summary>{t(`警告 ${warnings.length} 条`, `${warnings.length} warnings`)}</summary>
            <Issues issues={warnings} />
          </details>
        )}
        {shareable && !failed && (
          <>
            <Rule dashed />
            <p className={s.issuesHead}>{t("分享这一版", "Share this version")}</p>
            <MapShare versionId={v.id} />
          </>
        )}
        {!failed && (
          <p className={s.legend}>
            <PencilNote>{t("待确认", "to confirm")}</PencilNote>{" "}
            {t(
              `这条资料是占位，还没核实；依据它的结论要留意。资料状态按 ${v.dataAsOf} 算。`,
              `means the info is a placeholder that hasn't been checked; treat anything based on it with care. Data status is as of ${v.dataAsOf}.`
            )}
          </p>
        )}
      </Paper>

      {!failed && (
        <>
          {v.days.length > 1 && (
            <div className={s.dayPick} role="group" aria-label={t("地图上看哪一天", "Which day to show on the map")}>
              <Soft className={s.deskLabel}>{t("地图上看", "On the map")}</Soft>
              {v.days.map((d) => (
                <NoteButton key={d.dayNumber} pressed={shownDay === d.dayNumber} onClick={() => onShowDay(d.dayNumber)}>
                  {t(`第 ${d.dayNumber} 天`, `Day ${d.dayNumber}`)}
                </NoteButton>
              ))}
              <NoteButton pressed={shownDay === "all"} onClick={() => onShowDay("all")}>
                {t("全部", "All")}
              </NoteButton>
            </div>
          )}
          {shownDay === "all" && (
            <ul className={s.dayLegend} aria-label={t("地图上每天路线的颜色", "Route colour for each day on the map")}>
              {v.days.map((d) => (
                <li key={d.dayNumber}>
                  <span className={s.swatch} data-color={dayColor(d.dayNumber)} aria-hidden="true" />
                  {t(`第 ${d.dayNumber} 天（${DAY_COLOR_NAMES[dayColor(d.dayNumber)].zh}）`, `Day ${d.dayNumber} (${DAY_COLOR_NAMES[dayColor(d.dayNumber)].en})`)}
                </li>
              ))}
              <li>
                {t(
                  "虚线是步行，实线是公交地铁或打车；图钉上的“1-2”是第 1 天第 2 站",
                  "Dashed lines are walking, solid lines are bus/metro or taxi; “1-2” on a pin means day 1, stop 2"
                )}
              </li>
            </ul>
          )}
          {v.days.map((day) => (
            <DayCard key={day.dayNumber} day={day} issues={report.issues} order={v.routeOrder?.find((o) => o.dayNumber === day.dayNumber)} />
          ))}
        </>
      )}
    </>
  );
}
