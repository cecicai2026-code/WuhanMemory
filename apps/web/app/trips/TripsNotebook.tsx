"use client";

import { useCallback, useEffect, useState } from "react";
import type { TripConversation, TripVersionSummary } from "@wuhanmemory/shared";
import { BrassButton, Paper, PaperMark, PaperTitle, Rule, Soft, Stamp, TextLink } from "@/components/ui";
import { ShareControls } from "@/components/trip/ShareControls";
import { cityDate } from "@/lib/dates";
import { OwnerPasscodeForm } from "@/components/trip/OwnerPasscodeForm";
import { ApiError, listTrips } from "@/lib/planning-client";
import { useLang } from "@/components/i18n/LangProvider";
import { makeT, modelName } from "@/lib/i18n";
import s from "./trips.module.css";

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "passcode"; wrong: boolean }
  | { kind: "ready"; trips: TripConversation[] };

function cityTime(iso: string): string {
  return new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", hour: "2-digit", minute: "2-digit", hour12: false }).format(
    new Date(iso),
  );
}

function StatusStamp({ v }: { v: TripVersionSummary }) {
  const t = makeT(useLang());
  if (v.validationStatus === "passed") return <Stamp status="verified">{t("校验通过", "Checks passed")}</Stamp>;
  if (v.validationStatus === "warning") return <Stamp status="pending">{t("有警告", "Warnings")}</Stamp>;
  return <Stamp status="expired">{t("未通过", "Failed")}</Stamp>;
}

/** 一条印样：一个版本 */
function Proof({ v }: { v: TripVersionSummary }) {
  const lang = useLang();
  const t = makeT(lang);
  const failed = v.validationStatus === "failed";
  const when = v.startDate ? t(`${v.startDate.replaceAll("-", ".")} 出发`, `from ${v.startDate.replaceAll("-", ".")}`) : t("日期未定", "date not set");
  return (
    <li className={s.proof}>
      <div className={s.proofHead}>
        <p className={s.proofTitle}>
          {t(`第 ${v.versionNumber} 版`, `Version ${v.versionNumber}`)} · {failed ? t("没通过校验", "didn't pass the checks") : v.title}
        </p>
        <StatusStamp v={v} />
      </div>
      <p className={s.proofMeta}>
        {t(`${v.days} 天`, `${v.days} days`)} · {when} · {modelName(v.providerLabel, lang)}
        {v.model ? t(`（${v.model}）`, ` (${v.model})`) : ""} ·{" "}
        {t(`${cityDate(v.createdAt)} ${cityTime(v.createdAt)} 生成`, `made ${cityDate(v.createdAt)} ${cityTime(v.createdAt)}`)}
        {v.errorCount > 0 && t(` · 错误 ${v.errorCount} 条`, ` · ${v.errorCount} errors`)}
        {v.warningCount > 0 && t(` · 警告 ${v.warningCount} 条`, ` · ${v.warningCount} warnings`)}
      </p>
      {v.poiNames.length > 0 && <p className={s.proofPois}>{v.poiNames.join(" → ")}</p>}
      <div className={s.proofActions}>
        <TextLink href={`/trips/${v.id}`} onPaper>
          {t("打开 →", "Open →")}
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
  const tr = makeT(useLang());

  const fetchTrips = useCallback((afterPasscode = false) => {
    setLoad({ kind: "loading" });
    listTrips()
      .then((trips) => setLoad({ kind: "ready", trips }))
      .catch((err: unknown) => {
        // 公开模式下要网站主人的口令（板块 7）
        if (err instanceof ApiError && err.status === 401) setLoad({ kind: "passcode", wrong: afterPasscode });
        else setLoad({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
  }, []);

  useEffect(() => fetchTrips(), [fetchTrips]);

  if (load.kind === "loading") {
    return (
      <Paper className={s.notice}>
        <PaperMark>{tr("笔记本", "Notebook")}</PaperMark>
        <p role="status">{tr("正在翻笔记本……", "Leafing through the notebook…")}</p>
      </Paper>
    );
  }
  if (load.kind === "passcode") {
    return (
      <Paper className={s.notice}>
        <PaperMark>{tr("笔记本", "Notebook")}</PaperMark>
        <PaperTitle level={3}>{tr("我的行程只给网站主人看", "My Trips is for the site owner only")}</PaperTitle>
        <OwnerPasscodeForm wrong={load.wrong} onSaved={() => fetchTrips(true)} />
      </Paper>
    );
  }
  if (load.kind === "error") {
    return (
      <Paper className={s.notice}>
        <PaperMark>{tr("笔记本", "Notebook")}</PaperMark>
        <PaperTitle level={3}>{tr("行程暂时取不到", "Trips can't be fetched right now")}</PaperTitle>
        <p role="alert">{load.message}</p>
        <BrassButton onClick={() => fetchTrips()}>{tr("再试一次", "Try again")}</BrassButton>
      </Paper>
    );
  }
  if (load.trips.length === 0) {
    return (
      <Paper className={s.notice}>
        <PaperMark>{tr("笔记本", "Notebook")}</PaperMark>
        <PaperTitle level={3}>{tr("还没有行程", "No trips yet")}</PaperTitle>
        <p>
          {tr(
            "在地图工作台里说想怎么玩，排好的行程会收在这里，可以再打开，或者生成一个只读的分享链接。",
            "Describe a trip on the map workbench and the planned trips are kept here. You can open them again or make a read-only share link."
          )}
        </p>
        <BrassButton href="/map">{tr("去地图工作台", "Go to the map workbench")}</BrassButton>
      </Paper>
    );
  }

  return (
    <div className={s.notebook}>
      {load.trips.map((t) => (
        <Paper as="section" key={t.conversationId} className={s.page} aria-label={t.request ?? tr("一段对话", "A conversation")}>
          <PaperMark>
            {cityDate(t.updatedAt)} · {tr(`${t.itineraries.length} 份方案`, `${t.itineraries.length} plans`)}
          </PaperMark>
          <PaperTitle level={2} className={s.request}>
            {t.request ? `“${t.request}”` : tr("（这段对话没有记下第一句话）", "(The first message of this conversation wasn't saved)")}
          </PaperTitle>
          {t.itineraries.map((i) => (
            <div key={i.itineraryId} className={s.plan}>
              <Rule />
              <p className={s.planLabel}>
                <Soft>{i.emphasisLabel ?? tr("单份行程（多份方案之前排的）", "Single trip (planned before multiple plans existed)")}</Soft>
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
