"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { ItineraryVersion } from "@wuhanmemory/shared";
import { ItineraryCards } from "@/app/map/ItineraryCards";
import { MapPanel } from "@/app/map/MapPanel";
import { Paper, PaperMark, PaperTitle, Soft } from "@/components/ui";
import { cityDate } from "@/lib/dates";
import { itineraryPins, itineraryRoutes, type ShownDay } from "@/lib/itinerary-map";
import { useLang } from "@/components/i18n/LangProvider";
import { makeT, modelName } from "@/lib/i18n";
import s from "./trip.module.css";

const EMPHASIS_TEXT: Record<string, { zh: string; en: string }> = {
  classic: { zh: "经典必去", en: "The classics" },
  relaxed: { zh: "轻松少走路", en: "Easy, less walking" },
  culture: { zh: "深度文化", en: "Deep culture" },
};
const PACE_TEXT: Record<string, { zh: string; en: string }> = {
  relaxed: { zh: "轻松", en: "relaxed" },
  moderate: { zh: "适中", en: "moderate" },
  intensive: { zh: "紧凑", en: "packed" },
};

interface Props {
  version: ItineraryVersion;
  /** 明信片左上角的小字，例如"明信片 · 只读" */
  mark: string;
  /** 明信片下方的说明 */
  note: ReactNode;
  /** 明信片上的操作（我的行程里的分享按钮）；分享页不给 */
  actions?: ReactNode;
}

/**
 * 一份行程的只读视图（分享页 /s/[slug] 和我的行程 /trips/[versionId] 共用）。
 * 上面一张明信片：标题、天数和日期、侧重、谁排的、邮戳（行程生成的真实日期，设计规范 6.2）。
 * 下面左边是灯箱里的地图，右边是和 /map 一样的行程卡（逐日时间线、交通、景点资料和核实状态、校验结果）。
 * 没通过校验的行程只显示问题清单，地图上不画（和 /map 一样）。
 */
export function TripView({ version: v, mark, note, actions }: Props) {
  const [shownDay, setShownDay] = useState<ShownDay>(v.days[0]?.dayNumber ?? null);
  const routes = useMemo(() => itineraryRoutes(v, shownDay), [v, shownDay]);
  const pins = useMemo(() => itineraryPins(v, shownDay), [v, shownDay]);
  const lang = useLang();
  const t = makeT(lang);
  const start = v.frame.startDate ? v.frame.startDate.replaceAll("-", ".") : t("日期未定", "date not set");
  const emphasis = v.emphasis ? EMPHASIS_TEXT[v.emphasis] : undefined;
  const pace = PACE_TEXT[v.frame.pace];
  const facts = [
    t(`${v.frame.days} 天`, `${v.frame.days} days`),
    v.frame.startDate ? t(`${start} 出发`, `from ${start}`) : start,
    v.emphasis ? (emphasis ? t(emphasis.zh, emphasis.en) : v.emphasis) : null,
    pace ? t(`节奏${pace.zh}`, `${pace.en} pace`) : t(`节奏${v.frame.pace}`, `pace: ${v.frame.pace}`),
  ].filter(Boolean);

  return (
    <div className={s.view}>
      <Paper as="section" className={s.postcard} aria-label={t("行程明信片", "Trip postcard")}>
        <div className={s.postcardText}>
          <PaperMark>{mark}</PaperMark>
          <PaperTitle>{v.validation.status === "failed" ? t("这份行程没通过校验", "This trip didn't pass the checks") : v.title}</PaperTitle>
          <p className={s.facts}>{facts.join(" · ")}</p>
          <p className={s.by}>
            {t(
              `由 ${v.planner.providerLabel}${v.planner.model ? `（${v.planner.model}）` : ""}排，程序查交通、推钟点并校验`,
              `Planned by ${modelName(v.planner.providerLabel, lang)}${v.planner.model ? ` (${v.planner.model})` : ""}; the program looked up transport, worked out the times and ran the checks`
            )}
          </p>
          <Soft className={s.note}>{note}</Soft>
          {actions ? <div className={s.actions}>{actions}</div> : null}
        </div>
        <div className={s.postmark} aria-label={t(`生成于 ${cityDate(v.createdAt)}`, `Made ${cityDate(v.createdAt)}`)}>
          <span>{t("武汉", "WUHAN")}</span>
          <strong>{cityDate(v.createdAt)}</strong>
          <span>{t(`第 ${v.versionNumber} 版`, `Ver. ${v.versionNumber}`)}</span>
        </div>
      </Paper>

      <div className={s.body}>
        <section className={s.mapBox} aria-label={t("地图", "Map")}>
          <MapPanel pois={[]} poisError={null} routes={routes} pins={pins} />
        </section>
        <section className={s.cards} aria-label={t("逐日行程", "Day by day")}>
          <ItineraryCards version={v} loading={false} error={null} shownDay={shownDay} onShowDay={setShownDay} />
        </section>
      </div>
    </div>
  );
}
