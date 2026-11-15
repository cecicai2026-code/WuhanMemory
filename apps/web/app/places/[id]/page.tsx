import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Scene } from "@/components/shell/Scene";
import { TextLink } from "@/components/ui";
import { ApiUnavailableError, THEMES, getPlace, getPlaceWithList, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { StageToggle } from "@/components/stage/StageProvider";
import { both, categoryText } from "@/lib/format-poi";
import { getLang } from "@/lib/i18n-server";
import { makeT } from "@/lib/i18n";
import { rollsFrame } from "@/lib/scene3d/data";
import type { LineData } from "@/lib/scene3d/data";
import { LineStage } from "../LineStage";
import { ApiDown } from "../PlaceParts";
import { ClosedNote, StatusLegend, ThemeSheet, themeStatus } from "../ThemeSheet";
import s from "../places.module.css";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ debug?: string | string[] }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const lang = await getLang();
  const fallback = makeT(lang)("地点档案", "Places");
  try {
    return { title: (await getPlace(id, lang))?.poi.name ?? fallback };
  } catch {
    return { title: fallback };
  }
}

/**
 * 一个景点的详情：普通网页版，数据来自 GET /api/pois/{id}。
 * 四个主题是同一页上的四张信纸（./ThemeSheet.tsx），每张纸有锚点，所以 /places/yellow-crane-tower#tips 照样能分享。
 * 上沿的四个主题链接到主题页 /places/[id]/[主题]（纸页幕，板块 1B）。
 */
export default async function Page({ params, searchParams }: Props) {
  const { id } = await params;
  // 开发时 ?debug=nophoto：假装没有照片，看公开模式下的样子（和 /places 一样）
  const noPhoto = process.env.NODE_ENV !== "production" && (await searchParams).debug === "nophoto";
  const lang = await getLang();
  const t = makeT(lang);

  let data: Awaited<ReturnType<typeof getPlaceWithList>>;
  try {
    data = await getPlaceWithList(id, lang);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.place} title={t("地点档案", "Places")} back={{ href: "/places", label: t("回到胶卷", "Back to the film roll") }}>
        <ApiDown message={err.message} t={t} />
      </Scene>
    );
  }
  if (!data.place) notFound();

  const { poi, asOf } = data.place;
  const all = data.all;
  const index = all.findIndex((p) => p.id === poi.id);
  const prev = index > 0 ? all[index - 1] : undefined;
  const next = index >= 0 ? all[index + 1] : undefined;
  const sub = `${poi.district} · ${categoryText(poi.category, t)}`;

  // 立体版（晾片幕）用的数据：和下面的四张纸是同一份
  const stageData: LineData = {
    prints: all.map((p, i) => rollsFrame(noPhoto ? { ...p, coverPhoto: null } : p, i + 1, lang)),
    sel: poi.id,
    sub,
    topics: THEMES.map((th) => ({ id: th.id, name: both(th.name, t), status: themeStatus(poi, th) })),
    lang
  };

  return (
    <Scene
      scene={SCENES.place}
      count={t(`第 ${pad2(index + 1)} 张 / 共 ${pad2(all.length)} 张`, `Print ${pad2(index + 1)} of ${pad2(all.length)}`)}
      title={poi.name}
      kicker={sub}
      back={{ href: `/places?at=${encodeURIComponent(poi.id)}`, label: t("回到胶卷", "Back to the film roll") }}
      corner={<StageToggle />}
    >
      {index >= 0 && <LineStage data={stageData} />}
      <div className={s.detail}>
        <nav className={s.themes} aria-label={t("四个主题", "Four topics")}>
          {THEMES.map((th) => (
            <TextLink key={th.id} href={`/places/${poi.id}/${th.id}`}>
              {both(th.name, t)}
            </TextLink>
          ))}
        </nav>

        <StatusLegend asOf={asOf} t={t} />
        <ClosedNote poi={poi} t={t} />

        <div className={s.sheets}>
          {THEMES.map((theme, i) => (
            <ThemeSheet key={theme.id} poi={poi} theme={theme} tilt={i % 2 ? 0.5 : -0.5} t={t} />
          ))}
        </div>

        <nav className={s.pager} aria-label={t("其他景点", "Other places")}>
          {prev ? <TextLink href={`/places/${prev.id}`}>← {prev.name}</TextLink> : <span />}
          {next ? <TextLink href={`/places/${next.id}`}>{next.name} →</TextLink> : <span />}
        </nav>
      </div>
    </Scene>
  );
}
