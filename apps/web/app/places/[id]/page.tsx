import type { Metadata } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import type { PoiFact, PoiSource } from "@wuhanmemory/shared";
import { Scene } from "@/components/shell/Scene";
import { Paper, PaperMark, PaperTitle, Rule, Soft, Stamp, TextLink } from "@/components/ui";
import {
  formatDate,
  formatDuration,
  formatOpeningHours,
  formatPayment,
  formatReservation,
  formatTicket,
  formatTransport,
  sheetStatus
} from "@/lib/format-poi";
import { ApiUnavailableError, THEMES, getPlace, listPlaces, pad2 } from "@/lib/places";
import type { FieldKey, PoiDetail } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { ApiDown, Entry, GalleryEntry, ListEntry, ReviewsEntry, renderFood, renderPhotoSpot } from "../PlaceParts";
import s from "../places.module.css";

type Props = { params: Promise<{ id: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    return { title: (await getPlace(id))?.poi.name ?? "地点档案" };
  } catch {
    return { title: "地点档案" };
  }
}

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

function renderEntry(poi: PoiDetail, key: FieldKey, label: string): ReactNode {
  switch (key) {
    case "openingHours":
      return <Entry key={key} label={label} fact={poi.openingHours}>{poi.openingHours.value && formatOpeningHours(poi.openingHours.value)}</Entry>;
    case "ticket":
      return <Entry key={key} label={label} fact={poi.ticket}>{poi.ticket.value && formatTicket(poi.ticket.value)}</Entry>;
    case "reservation":
      return <Entry key={key} label={label} fact={poi.reservation}>{poi.reservation.value && formatReservation(poi.reservation.value)}</Entry>;
    case "payment":
      return <Entry key={key} label={label} fact={poi.payment}>{poi.payment.value && formatPayment(poi.payment.value)}</Entry>;
    case "transport":
      return <Entry key={key} label={label} fact={poi.transport}>{poi.transport.value && formatTransport(poi.transport.value)}</Entry>;
    case "recommendedDurationMinutes": {
      const f = poi.recommendedDurationMinutes;
      return <Entry key={key} label={label} fact={f}>{f.value != null && formatDuration(f.value)}</Entry>;
    }
    case "photoSpots":
      return <ListEntry key={key} label={label} facts={poi.photoSpots} render={renderPhotoSpot} />;
    case "food":
      return <ListEntry key={key} label={label} facts={poi.food} render={renderFood} />;
    case "reviews":
      return <ReviewsEntry key={key} reviews={poi.reviews} />;
    case "photos":
      return <GalleryEntry key={key} photos={poi.photos} />;
    default:
      return <Entry key={key} label={label} fact={poi[key]}>{poi[key].value}</Entry>;
  }
}

/**
 * 一个景点的详情：普通网页版，数据来自 GET /api/pois/{id}。
 * 四个主题（景点概览、游玩建议、景点图册、周边美食）是同一页上的四张信纸，上沿的索引用锚点跳转，
 * 所以 /places/yellow-crane-tower#tips 这样的地址可以直接分享。
 * 每个条目下面写着怎么核实的、来源和核实日期；官网占位的盖"待确认"，过期的盖"已过期"。
 * 数据里没有的条目显示手写的"待补充"，不编内容。
 */
export default async function Page({ params }: Props) {
  const { id } = await params;

  let res: Awaited<ReturnType<typeof getPlace>>;
  let all: Awaited<ReturnType<typeof listPlaces>>["pois"];
  try {
    [res, { pois: all }] = await Promise.all([getPlace(id), listPlaces()]);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.place} title="地点档案" back={{ href: "/places", label: "回到胶卷" }}>
        <ApiDown message={err.message} />
      </Scene>
    );
  }
  if (!res) notFound();

  const { poi, asOf } = res;
  const index = all.findIndex((p) => p.id === poi.id);
  const no = index + 1;
  const prev = index > 0 ? all[index - 1] : undefined;
  const next = index >= 0 ? all[index + 1] : undefined;

  return (
    <Scene
      scene={SCENES.place}
      count={`第 ${pad2(no)} 张 / 共 ${pad2(all.length)} 张`}
      title={poi.name}
      kicker={poi.district}
      back={{ href: "/places", label: "回到胶卷" }}
    >
      <div className={s.detail}>
        <nav className={s.themes} aria-label="四个主题">
          {THEMES.map((t) => (
            <TextLink key={t.id} href={`#${t.id}`}>
              {t.name}
            </TextLink>
          ))}
        </nav>

        <p className={s.legend}>
          已核实：实地核实或核对过来源。待确认：先按官网填的占位。已过期：过了有效期，要重新核实。状态按 {formatDate(asOf)} 计算。
        </p>

        <div className={s.sheets}>
          {THEMES.map((theme, i) => {
            const facts = theme.fields.flatMap((f) => factsOf(poi, f.key));
            const sources = new Map<string, PoiSource>();
            for (const f of facts) if (f.source && f.status !== "missing") sources.set(f.source.id, f.source);
            // 图册和评价没有逐条的核实信息；图册里有占位照片时整张纸算待确认
            const status =
              theme.id === "gallery"
                ? poi.photos.length === 0 || poi.photos.some((p) => p.placeholder)
                  ? "pending"
                  : "verified"
                : sheetStatus(facts);
            return (
              <Paper key={theme.id} id={theme.id} as="section" className={s.sheet} tilt={i % 2 ? 0.5 : -0.5} aria-label={theme.name}>
                <PaperMark>
                  {poi.name} · {pad2(i + 1)} / {pad2(THEMES.length)}
                </PaperMark>
                <PaperTitle>{theme.name}</PaperTitle>
                <Rule />
                <dl className={s.entries}>{theme.fields.map((f) => renderEntry(poi, f.key, f.label))}</dl>
                <div className={s.sheetFoot}>
                  <div>
                    <p>来源：</p>
                    {sources.size === 0 ? (
                      <p>
                        <Soft>本页暂无</Soft>
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
                                · {src.type === "field-visit" ? "走访" : "查阅"}于 {formatDate(src.accessedAt)}
                              </Soft>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <Stamp status={status} />
                </div>
              </Paper>
            );
          })}
        </div>

        <nav className={s.pager} aria-label="其他景点">
          {prev ? <TextLink href={`/places/${prev.id}`}>← {prev.name}</TextLink> : <span />}
          {next ? <TextLink href={`/places/${next.id}`}>{next.name} →</TextLink> : <span />}
        </nav>
      </div>
    </Scene>
  );
}
