"use client";

import type { ReactNode } from "react";
import type {
  FactStatus,
  ItineraryDay,
  ItineraryLeg,
  ItineraryStop,
  ItineraryVersion,
  PoiFact,
  ValidationIssue,
} from "@wuhanmemory/shared";
import { NoteButton, Paper, PaperMark, PaperTitle, PencilNote, Rule, Soft, Stamp, TextLink } from "@/components/ui";
import { formatOpeningHours, formatPayment, formatReservation, formatTicket } from "@/lib/format-poi";
import s from "./map.module.css";

const WEEKDAY = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const MODE_TEXT = { walk: "步行", transit: "公交地铁", drive: "打车" } as const;
/** 这几种问题说的是两站之间的交通，标在交通那一行，不标在景点上 */
const LEG_CODES = new Set(["overlap", "transport-too-short", "transport-tight", "route-unknown", "route-stale"]);
/** 这两种问题在每条资料旁边已经用"待确认""待补充"标出来了，景点下面不再重复 */
const FACT_CODES = new Set(["data-pending", "data-missing"]);

function dayLabel(day: ItineraryDay): string {
  if (!day.date) return `第 ${day.dayNumber} 天 · 日期未定`;
  const d = new Date(`${day.date}T00:00:00`);
  return `第 ${day.dayNumber} 天 · ${day.date.slice(5).replace("-", ".")} ${WEEKDAY[d.getDay()]}`;
}

function FactTag({ status }: { status: FactStatus }) {
  if (status === "verified") return null;
  const text = { pending: "待确认", missing: "待补充", expired: "已过期" }[status];
  return (
    <span className={s.factTag} data-status={status}>
      {text}
    </span>
  );
}

function Fact<T>({ label, fact, format }: { label: string; fact: PoiFact<T>; format: (v: T) => string }) {
  const text = fact.value !== null && fact.value !== undefined ? format(fact.value) : "没有资料";
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
  if (!issues.length) return null;
  return (
    <ul className={s.issues}>
      {issues.map((i, n) => (
        <li key={n} data-level={i.level}>
          <span aria-hidden="true">{i.level === "error" ? "✕" : "!"}</span>
          <span className="sr-only">{i.level === "error" ? "错误：" : "警告："}</span>
          {i.message}
        </li>
      ))}
    </ul>
  );
}

function Leg({ leg, issues }: { leg: ItineraryLeg | undefined; issues: ValidationIssue[] }) {
  const r = leg?.route;
  const ok = r && r.status === "ok" && r.durationMinutes != null;
  return (
    <li className={s.leg}>
      <p>
        <span aria-hidden="true">↓ </span>
        {ok ? (
          <>
            <strong>
              {MODE_TEXT[r.mode]} {r.durationMinutes} 分钟
            </strong>
            {r.distanceMeters != null && ` · ${(r.distanceMeters / 1000).toFixed(1)} 公里`}
            {r.cost?.amountCny != null && r.cost.kind !== "free" && ` · 约 ${r.cost.amountCny} 元`}
            {r.summary && ` · ${r.summary}`}
          </>
        ) : (
          <strong>交通没查到</strong>
        )}
      </p>
      {leg && (
        <p className={s.legMeta}>
          {leg.choice}
          {r?.checkedAt && ` · 高德，${r.checkedAt.slice(5, 10).replace("-", ".")} 查询`}
          {r?.cache === "stale" && " · 缓存已过期"}
        </p>
      )}
      <Issues issues={issues} />
    </li>
  );
}

function Stop({ stop, issues }: { stop: ItineraryStop; issues: ValidationIssue[] }) {
  const f = stop.facts;
  return (
    <li className={s.stop}>
      <p className={s.stopTime}>
        {stop.arrive}–{stop.leave}
      </p>
      <p className={s.stopName}>
        <TextLink href={`/places/${stop.poiId}`} onPaper>
          {stop.name}
        </TextLink>{" "}
        <Soft>{stop.district}</Soft>
      </p>
      {stop.reason && <p className={s.stopReason}>{stop.reason}</p>}
      <dl className={s.facts}>
        <Fact label="开放" fact={f.openingHours} format={formatOpeningHours} />
        <Fact label="预约" fact={f.reservation} format={formatReservation} />
        <Fact label="门票" fact={f.ticket} format={formatTicket} />
        <Fact label="支付" fact={f.payment} format={formatPayment} />
      </dl>
      <Issues issues={issues} />
    </li>
  );
}

function DayCard({ day, issues, tilt }: { day: ItineraryDay; issues: ValidationIssue[]; tilt: number }) {
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
    <Paper kind="card" tilt={tilt} as="article" aria-label={dayLabel(day)}>
      <div className={s.cardHead}>
        <PaperMark>{dayLabel(day)}</PaperMark>
        <Stamp status={hasWarning ? "pending" : "verified"}>{hasWarning ? "有警告" : "通过"}</Stamp>
      </div>
      <PaperTitle level={3}>{day.theme || `第 ${day.dayNumber} 天`}</PaperTitle>
      <Issues issues={dayWide} />
      <ol className={s.timeline}>{items}</ol>
    </Paper>
  );
}

interface Props {
  version: ItineraryVersion | null;
  loading: boolean;
  error: string | null;
  shownDay: number | null;
  onShowDay: (day: number) => void;
}

/**
 * 右边的索引卡：行程（设计规范 9.1）。
 * 第一张是总卡：校验结果的印章、用的模型、按默认补上的设置、每一条错误和警告。
 * 没通过校验的行程只显示问题清单，不显示时间线，地图上也不画（2026-11-15 Cecilia 确认）。
 * 其余每天一张：时间线、每段交通（高德查的真实时间）、预约和支付提示（景点库里的资料，旁边标着待确认、待补充）。
 */
export function ItineraryCards({ version, loading, error, shownDay, onShowDay }: Props) {
  if (loading) {
    return (
      <Paper kind="card" tilt={1}>
        <PaperMark>索引卡 · 行程</PaperMark>
        <p>正在取行程……</p>
      </Paper>
    );
  }
  if (error) {
    return (
      <Paper kind="card" tilt={1}>
        <PaperMark>索引卡 · 行程</PaperMark>
        <p className={s.routeError} role="alert">
          没取到行程：{error}
        </p>
      </Paper>
    );
  }
  if (!version) {
    return (
      <Paper kind="card" tilt={1}>
        <PaperMark>索引卡 · 行程</PaperMark>
        <PaperTitle level={3}>还没有行程</PaperTitle>
        <p>在左边的打字纸上说想怎么玩。排好、校验过的行程会出现在这里，每天一张卡，地图上同时画出路线。</p>
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
      <Stamp status="verified">校验通过</Stamp>
    ) : report.status === "warning" ? (
      <Stamp status="pending">有警告</Stamp>
    ) : (
      <Stamp status="expired">未通过</Stamp>
    );
  const planner = v.planner;

  return (
    <>
      <Paper kind="card" tilt={-1} as="section" aria-label="行程总卡">
        <div className={s.cardHead}>
          <PaperMark>行程 · 第 {v.versionNumber} 版</PaperMark>
          {stamp}
        </div>
        <PaperTitle level={3}>{failed ? "这份行程没通过校验" : v.title}</PaperTitle>
        <p className={s.routeMeta}>
          {planner.providerLabel}
          {planner.model ? ` · ${planner.model}` : ""}
          {planner.rounds === 2 ? ` · 第一版有 ${planner.firstRoundErrors} 处错误，修正过一次` : " · 一次生成"}
        </p>
        {failed && <p>修正一次后仍有 {errors.length} 处错误，所以不展示时间线，地图上也不画。可以换个说法或调整要求再发一次。</p>}
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
            <p className={s.issuesHead}>错误 {errors.length} 条</p>
            <Issues issues={errors} />
          </>
        )}
        {warnings.length > 0 && (
          <details className={s.warnings} open={failed || warnings.length <= 4}>
            <summary>警告 {warnings.length} 条</summary>
            <Issues issues={warnings} />
          </details>
        )}
        {!failed && (
          <p className={s.legend}>
            <PencilNote>待确认</PencilNote> 这条资料是占位，还没核实；依据它的结论要留意。资料状态按 {v.dataAsOf} 算。
          </p>
        )}
      </Paper>

      {!failed && (
        <>
          {v.days.length > 1 && (
            <div className={s.dayPick} role="group" aria-label="地图上看哪一天">
              <Soft>地图上看</Soft>
              {v.days.map((d) => (
                <NoteButton key={d.dayNumber} pressed={shownDay === d.dayNumber} onClick={() => onShowDay(d.dayNumber)}>
                  第 {d.dayNumber} 天
                </NoteButton>
              ))}
            </div>
          )}
          {v.days.map((day, i) => (
            <DayCard key={day.dayNumber} day={day} issues={report.issues} tilt={i % 2 ? 1 : -1} />
          ))}
        </>
      )}
    </>
  );
}
