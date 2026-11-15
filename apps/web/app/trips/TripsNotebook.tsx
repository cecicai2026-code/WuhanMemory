"use client";

import { useCallback, useEffect, useState } from "react";
import type { TripConversation, TripVersionSummary } from "@wuhanmemory/shared";
import { BrassButton, Paper, PaperMark, PaperTitle, Rule, Soft, Stamp, TextLink } from "@/components/ui";
import { ShareControls } from "@/components/trip/ShareControls";
import { cityDate } from "@/lib/dates";
import { listTrips } from "@/lib/planning-client";
import s from "./trips.module.css";

type Load = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; trips: TripConversation[] };

function cityTime(iso: string): string {
  return new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", hour: "2-digit", minute: "2-digit", hour12: false }).format(
    new Date(iso),
  );
}

function StatusStamp({ v }: { v: TripVersionSummary }) {
  if (v.validationStatus === "passed") return <Stamp status="verified">校验通过</Stamp>;
  if (v.validationStatus === "warning") return <Stamp status="pending">有警告</Stamp>;
  return <Stamp status="expired">未通过</Stamp>;
}

/** 一条印样：一个版本 */
function Proof({ v }: { v: TripVersionSummary }) {
  const failed = v.validationStatus === "failed";
  const when = v.startDate ? `${v.startDate.replaceAll("-", ".")} 出发` : "日期未定";
  return (
    <li className={s.proof}>
      <div className={s.proofHead}>
        <p className={s.proofTitle}>
          第 {v.versionNumber} 版 · {failed ? "没通过校验" : v.title}
        </p>
        <StatusStamp v={v} />
      </div>
      <p className={s.proofMeta}>
        {v.days} 天 · {when} · {v.providerLabel}
        {v.model ? `（${v.model}）` : ""} · {cityDate(v.createdAt)} {cityTime(v.createdAt)} 生成
        {v.errorCount > 0 && ` · 错误 ${v.errorCount} 条`}
        {v.warningCount > 0 && ` · 警告 ${v.warningCount} 条`}
      </p>
      {v.poiNames.length > 0 && <p className={s.proofPois}>{v.poiNames.join(" → ")}</p>}
      <div className={s.proofActions}>
        <TextLink href={`/trips/${v.id}`} onPaper>
          打开 →
        </TextLink>
        <ShareControls versionId={v.id} failed={failed} initial={v.share} />
      </div>
    </li>
  );
}

/**
 * 我的行程（设计规范 9.3，笔记本）：/map 上生成过的行程，按对话分组，最近的在前。
 * 一段对话里按侧重分几份，每份列出它的全部版本（新版本在前），每个版本能打开、能生成或撤回分享链接。
 */
export function TripsNotebook() {
  const [load, setLoad] = useState<Load>({ kind: "loading" });

  const fetchTrips = useCallback(() => {
    setLoad({ kind: "loading" });
    listTrips()
      .then((trips) => setLoad({ kind: "ready", trips }))
      .catch((err: unknown) => setLoad({ kind: "error", message: err instanceof Error ? err.message : String(err) }));
  }, []);

  useEffect(fetchTrips, [fetchTrips]);

  if (load.kind === "loading") {
    return (
      <Paper className={s.notice}>
        <PaperMark>笔记本</PaperMark>
        <p role="status">正在翻笔记本……</p>
      </Paper>
    );
  }
  if (load.kind === "error") {
    return (
      <Paper className={s.notice}>
        <PaperMark>笔记本</PaperMark>
        <PaperTitle level={3}>行程暂时取不到</PaperTitle>
        <p role="alert">{load.message}</p>
        <BrassButton onClick={fetchTrips}>再试一次</BrassButton>
      </Paper>
    );
  }
  if (load.trips.length === 0) {
    return (
      <Paper className={s.notice}>
        <PaperMark>笔记本</PaperMark>
        <PaperTitle level={3}>还没有行程</PaperTitle>
        <p>在地图工作台里说想怎么玩，排好的行程会收在这里，可以再打开，或者生成一个只读的分享链接。</p>
        <BrassButton href="/map">去地图工作台</BrassButton>
      </Paper>
    );
  }

  return (
    <div className={s.notebook}>
      {load.trips.map((t) => (
        <Paper as="section" key={t.conversationId} className={s.page} aria-label={t.request ?? "一段对话"}>
          <PaperMark>
            {cityDate(t.updatedAt)} · {t.itineraries.length} 份方案
          </PaperMark>
          <PaperTitle level={2} className={s.request}>
            {t.request ? `“${t.request}”` : "（这段对话没有记下第一句话）"}
          </PaperTitle>
          {t.itineraries.map((i) => (
            <div key={i.itineraryId} className={s.plan}>
              <Rule />
              <p className={s.planLabel}>
                <Soft>{i.emphasisLabel ?? "单份行程（多份方案之前排的）"}</Soft>
              </p>
              <ol className={s.proofs}>
                {i.versions.map((v) => (
                  <Proof key={v.id} v={v} />
                ))}
              </ol>
            </div>
          ))}
        </Paper>
      ))}
    </div>
  );
}
