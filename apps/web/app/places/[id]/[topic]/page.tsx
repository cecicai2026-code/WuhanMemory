import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Scene } from "@/components/shell/Scene";
import { TextLink } from "@/components/ui";
import { ApiUnavailableError, THEMES, findTheme, getPlace, getPlaceWithList, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { both } from "@/lib/format-poi";
import { getLang } from "@/lib/i18n-server";
import { makeT } from "@/lib/i18n";
import { StageToggle } from "@/components/stage/StageProvider";
import type { SheetData } from "@/lib/scene3d/data";
import { SheetStage } from "../../SheetStage";
import { ApiDown } from "../../PlaceParts";
import { ClosedNote, StatusLegend, ThemeSheet } from "../../ThemeSheet";
import s from "../../places.module.css";

type Props = { params: Promise<{ id: string; topic: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id, topic } = await params;
  const theme = findTheme(topic);
  const lang = await getLang();
  const t = makeT(lang);
  try {
    const name = (await getPlace(id, lang))?.poi.name;
    return { title: name && theme ? `${name} · ${both(theme.name, t)}` : t("地点档案", "Places") };
  } catch {
    return { title: t("地点档案", "Places") };
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
  const lang = await getLang();
  const t = makeT(lang);

  let data: Awaited<ReturnType<typeof getPlaceWithList>>;
  try {
    data = await getPlaceWithList(id, lang);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.sheet} title={t("地点档案", "Places")} back={{ href: `/places/${encodeURIComponent(id)}`, label: t("回到晾片", "Back to the drying line") }}>
        <ApiDown message={err.message} t={t} />
      </Scene>
    );
  }
  if (!data.place) notFound();

  const { poi, asOf } = data.place;
  const k = THEMES.indexOf(theme);
  const themeName = both(theme.name, t);
  const stageData: SheetData = { id: poi.id, topic: theme.id, topics: THEMES.map((th) => ({ id: th.id, name: both(th.name, t) })), lang };

  return (
    <Scene
      scene={SCENES.sheet}
      count={t(`第 ${pad2(k + 1)} 页 / 共 ${pad2(THEMES.length)} 页`, `Page ${pad2(k + 1)} of ${pad2(THEMES.length)}`)}
      title={`${poi.name} · ${themeName}`}
      kicker={poi.district}
      back={{ href: `/places/${poi.id}`, label: t("回到晾片", "Back to the drying line") }}
      corner={<StageToggle />}
    >
      <SheetStage data={stageData} />
      {/* 立体模式下这一块照样显示，浮在桌面上（data-stage-show）；标题由纸上的大字代替 */}
      <div className={`${s.detail} ${s.sheetPage}`} data-stage-show>
        <StatusLegend asOf={asOf} t={t} />
        <ClosedNote poi={poi} t={t} />

        {/* key：换主题时重新挂上，落下和显影重新播放。--chars：标题逐字打出用 */}
        <div key={theme.id} className={s.sheetDrop} data-stage-paper style={{ "--chars": themeName.length } as React.CSSProperties}>
          <ThemeSheet poi={poi} theme={theme} tilt={-0.5} t={t} />
        </div>

        <nav className={s.topicIndex} aria-label={t("四个主题", "Four topics")}>
          {THEMES.map((th, i) => (
            <TextLink key={th.id} href={`/places/${poi.id}/${th.id}`} current={th.id === theme.id}>
              {pad2(i + 1)} {both(th.name, t)}
            </TextLink>
          ))}
        </nav>
      </div>
    </Scene>
  );
}
