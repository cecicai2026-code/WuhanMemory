import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Scene } from "@/components/shell/Scene";
import { TextLink } from "@/components/ui";
import { ApiUnavailableError, THEMES, getPlace, getPlaceWithList, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { ApiDown } from "../PlaceParts";
import { ClosedNote, StatusLegend, ThemeSheet } from "../ThemeSheet";
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

/**
 * 一个景点的详情：普通网页版，数据来自 GET /api/pois/{id}。
 * 四个主题是同一页上的四张信纸（./ThemeSheet.tsx），每张纸有锚点，所以 /places/yellow-crane-tower#tips 照样能分享。
 * 上沿的四个主题链接到主题页 /places/[id]/[主题]（纸页幕，板块 1B）。
 */
export default async function Page({ params }: Props) {
  const { id } = await params;

  let data: Awaited<ReturnType<typeof getPlaceWithList>>;
  try {
    data = await getPlaceWithList(id);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.place} title="地点档案" back={{ href: "/places", label: "回到胶卷" }}>
        <ApiDown message={err.message} />
      </Scene>
    );
  }
  if (!data.place) notFound();

  const { poi, asOf } = data.place;
  const all = data.all;
  const index = all.findIndex((p) => p.id === poi.id);
  const prev = index > 0 ? all[index - 1] : undefined;
  const next = index >= 0 ? all[index + 1] : undefined;

  return (
    <Scene
      scene={SCENES.place}
      count={`第 ${pad2(index + 1)} 张 / 共 ${pad2(all.length)} 张`}
      title={poi.name}
      kicker={poi.district}
      back={{ href: "/places", label: "回到胶卷" }}
    >
      <div className={s.detail}>
        <nav className={s.themes} aria-label="四个主题">
          {THEMES.map((t) => (
            <TextLink key={t.id} href={`/places/${poi.id}/${t.id}`}>
              {t.name}
            </TextLink>
          ))}
        </nav>

        <StatusLegend asOf={asOf} />
        <ClosedNote poi={poi} />

        <div className={s.sheets}>
          {THEMES.map((theme, i) => (
            <ThemeSheet key={theme.id} poi={poi} theme={theme} tilt={i % 2 ? 0.5 : -0.5} />
          ))}
        </div>

        <nav className={s.pager} aria-label="其他景点">
          {prev ? <TextLink href={`/places/${prev.id}`}>← {prev.name}</TextLink> : <span />}
          {next ? <TextLink href={`/places/${next.id}`}>{next.name} →</TextLink> : <span />}
        </nav>
      </div>
    </Scene>
  );
}
