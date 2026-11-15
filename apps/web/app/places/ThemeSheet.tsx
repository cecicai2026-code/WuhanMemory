/**
 * 一个景点的一个主题（景点概览、游玩建议、景点图册、周边美食）写在一张信纸上。
 * 详情页 /places/[id] 上四张纸、主题页 /places/[id]/[主题] 上一张纸用的都是这里，
 * 立体的纸页幕也用同一张纸（真实的网页文字，设计规范第 15 节第 4 条）。
 *
 * 每个条目下面写着怎么核实的、来源和核实日期；过期的把过期日期加粗。
 * 条目旁不盖章，每张纸只在右下角盖一个章：有过期的盖"已过期"，有待确认或待补充的盖"待确认"。
 * 数据里没有的条目显示手写的"待补充"，不编内容。
 */
import type { ReactNode } from "react";
import type { PoiFact, PoiSource } from "@wuhanmemory/shared";
import { Paper, PaperMark, PaperTitle, Rule, Soft, Stamp } from "@/components/ui";
import {
  both,
  formatDate,
  formatDuration,
  formatOpeningHours,
  formatPayment,
  formatReservation,
  formatTicket,
  formatTransport,
  sheetStatus
} from "@/lib/format-poi";
import { THEMES, pad2 } from "@/lib/places";
import type { T } from "@/lib/i18n";
import type { FieldKey, PoiDetail, Theme } from "@/lib/places";
import { Entry, FactMeta, GalleryEntry, ListEntry, ReviewsEntry, renderFood, renderPhotoSpot } from "./PlaceParts";
import s from "./places.module.css";

/** 一个条目用到的信息（算这张纸的状态、列这张纸的来源用） */
function factsOf(poi: PoiDetail, key: FieldKey): Array<PoiFact<unknown>> {
  switch (key) {
    case "photoSpots":
      return poi.photoSpots;
    case "food":
      return poi.food;
    case "reviews":
    case "photos":
      return [];
    default:
      return [poi[key]];
  }
}

function renderEntry(poi: PoiDetail, key: FieldKey, label: string, t: T): ReactNode {
  switch (key) {
    case "openingHours":
      return <Entry key={key} label={label} fact={poi.openingHours} t={t}>{poi.openingHours.value && formatOpeningHours(poi.openingHours.value, t)}</Entry>;
    case "ticket":
      return <Entry key={key} label={label} fact={poi.ticket} t={t}>{poi.ticket.value && formatTicket(poi.ticket.value, t)}</Entry>;
    case "reservation":
      return <Entry key={key} label={label} fact={poi.reservation} t={t}>{poi.reservation.value && formatReservation(poi.reservation.value, t)}</Entry>;
    case "payment":
      return <Entry key={key} label={label} fact={poi.payment} t={t}>{poi.payment.value && formatPayment(poi.payment.value, t)}</Entry>;
    case "transport":
      return <Entry key={key} label={label} fact={poi.transport} t={t}>{poi.transport.value && formatTransport(poi.transport.value, t)}</Entry>;
    case "recommendedDurationMinutes": {
      const f = poi.recommendedDurationMinutes;
      return <Entry key={key} label={label} fact={f} t={t}>{f.value != null && formatDuration(f.value, t)}</Entry>;
    }
    case "photoSpots":
      return <ListEntry key={key} label={label} facts={poi.photoSpots} render={(v) => renderPhotoSpot(v, t)} t={t} />;
    case "food":
      return <ListEntry key={key} label={label} facts={poi.food} render={(v) => renderFood(v, t)} t={t} />;
    case "reviews":
      return <ReviewsEntry key={key} label={label} reviews={poi.reviews} t={t} />;
    case "photos":
      return <GalleryEntry key={key} label={label} photos={poi.photos} t={t} />;
    default:
      return <Entry key={key} label={label} fact={poi[key]} t={t}>{poi[key].value}</Entry>;
  }
}

/** 这张纸盖哪个章 */
export function themeStatus(poi: PoiDetail, theme: Theme): "verified" | "pending" | "expired" {
  // 图册和评价没有逐条的核实信息；图册里有占位照片时整张纸算待确认
  if (theme.id === "gallery") return poi.photos.length === 0 || poi.photos.some((p) => p.placeholder) ? "pending" : "verified";
  return sheetStatus(theme.fields.flatMap((f) => factsOf(poi, f.key)));
}

export function ThemeSheet({ poi, theme, tilt, className, t }: { poi: PoiDetail; theme: Theme; tilt?: number; className?: string; t: T }) {
  const i = THEMES.findIndex((th) => th.id === theme.id);
  const name = both(theme.name, t);
  const facts = theme.fields.flatMap((f) => factsOf(poi, f.key));
  const sources = new Map<string, PoiSource>();
  for (const f of facts) {
    if (f.status === "missing") continue;
    for (const src of [f.source, ...f.extraSources]) if (src) sources.set(src.id, src);
  }
  return (
    <Paper id={theme.id} as="section" className={className ? `${s.sheet} ${className}` : s.sheet} tilt={tilt} aria-label={name}>
      <PaperMark>
        {poi.name} · {pad2(i + 1)} / {pad2(THEMES.length)}
      </PaperMark>
      <PaperTitle>{name}</PaperTitle>
      <Rule />
      <dl className={s.entries}>{theme.fields.map((f) => renderEntry(poi, f.key, both(f.label, t), t))}</dl>
      <div className={s.sheetFoot}>
        <div>
          <p>{t("来源：", "Sources:")}</p>
          {sources.size === 0 ? (
            <p>
              <Soft>{t("本页暂无", "None on this page")}</Soft>
            </p>
          ) : (
            <ul className={s.sourceList}>
              {[...sources.values()].map((src) => (
                <li key={src.id}>
                  {src.url ? (
                    <a href={src.url} target="_blank" rel="noreferrer">
                      {src.title}
                    </a>
                  ) : (
                    src.title
                  )}
                  {src.accessedAt && (
                    <Soft>
                      {" "}
                      · {src.type === "field-visit" ? t("走访于", "visited") : t("查阅于", "accessed")} {formatDate(src.accessedAt)}
                    </Soft>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <Stamp status={themeStatus(poi, theme)} />
      </div>
    </Paper>
  );
}

/** 纸上面那行说明：三种状态是什么意思、按哪一天算 */
export function StatusLegend({ asOf, t }: { asOf: string; t: T }) {
  return (
    <p className={s.legend}>
      {t(
        `已核实：实地核实或核对过来源。待确认：先用官网、旅游平台或媒体资料占位，还没核实。已过期：过了有效期，要重新核实。状态按 ${formatDate(asOf)} 计算。`,
        `Verified: checked on site or against the source. To confirm: a placeholder from an official site, travel platform or news report, not yet checked. Expired: past its valid-until date and needs checking again. Statuses are as of ${formatDate(asOf)}. The English place texts are translations of the Chinese records, made by Claude (an AI) and not yet checked by a person.`
      )}
    </p>
  );
}

/** 暂停开放的说明 */
export function ClosedNote({ poi, t }: { poi: PoiDetail; t: T }) {
  const st = poi.operatingStatus;
  if (st?.value?.code !== "closed-temporarily") return null;
  return (
    <div className={s.closed} role="note">
      <p>
        <strong>{t("暂停开放", "Temporarily closed")}</strong>
        {st.value.reopenExpected && t(`，预计 ${formatDate(st.value.reopenExpected)} 恢复`, `, expected to reopen ${formatDate(st.value.reopenExpected)}`)}
        {st.value.reopenNote && t(`（${st.value.reopenNote}）`, ` (${st.value.reopenNote})`)}
        {t("。排行程时不会选这里。", ". Trip plans won't include it.")}
      </p>
      {st.value.note && <p>{st.value.note}</p>}
      <FactMeta fact={st} t={t} />
    </div>
  );
}
