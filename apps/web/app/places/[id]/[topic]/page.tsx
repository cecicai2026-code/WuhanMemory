import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Scene } from "@/components/shell/Scene";
import { TextLink } from "@/components/ui";
import { ApiUnavailableError, THEMES, findTheme, getPlace, getPlaceWithList, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { ApiDown } from "../../PlaceParts";
import { ClosedNote, StatusLegend, ThemeSheet } from "../../ThemeSheet";
import s from "../../places.module.css";

type Props = { params: Promise<{ id: string; topic: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id, topic } = await params;
  const theme = findTheme(topic);
  try {
    const name = (await getPlace(id))?.poi.name;
    return { title: name && theme ? `${name} · ${theme.name}` : "地点档案" };
  } catch {
    return { title: "地点档案" };
  }
}

/**
 * 纸页幕的普通版（设计规范第 15 节第 12 条）：一个景点的一个主题，只有这一张纸，
 * 下面是四个主题的索引。地址里的主题是 overview、tips、gallery、food（lib/places.ts 的 THEMES）。
 * 数据和详情页同一个入口（getPlaceWithList），纸和详情页同一个组件（ThemeSheet）。
 */
export default async function Page({ params }: Props) {
  const { id, topic } = await params;
  const theme = findTheme(topic);
  if (!theme) notFound();

  let data: Awaited<ReturnType<typeof getPlaceWithList>>;
  try {
    data = await getPlaceWithList(id);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.sheet} title="地点档案" back={{ href: `/places/${encodeURIComponent(id)}`, label: "回到晾片" }}>
        <ApiDown message={err.message} />
      </Scene>
    );
  }
  if (!data.place) notFound();

  const { poi, asOf } = data.place;
  const t = THEMES.indexOf(theme);

  return (
    <Scene
      scene={SCENES.sheet}
      count={`第 ${pad2(t + 1)} 页 / 共 ${pad2(THEMES.length)} 页`}
      title={`${poi.name} · ${theme.name}`}
      kicker={poi.district}
      back={{ href: `/places/${poi.id}`, label: "回到晾片" }}
    >
      <div className={s.detail}>
        <StatusLegend asOf={asOf} />
        <ClosedNote poi={poi} />

        <ThemeSheet poi={poi} theme={theme} tilt={-0.5} />

        <nav className={s.topicIndex} aria-label="四个主题">
          {THEMES.map((th, i) => (
            <TextLink key={th.id} href={`/places/${poi.id}/${th.id}`} current={th.id === theme.id}>
              {pad2(i + 1)} {th.name}
            </TextLink>
          ))}
        </nav>
      </div>
    </Scene>
  );
}
