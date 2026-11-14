import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Scene } from "@/components/shell/Scene";
import { Paper, PaperMark, PaperTitle, PencilNote, Rule, Stamp, TextLink } from "@/components/ui";
import { IS_SAMPLE, THEMES, frameNo, getPlace, listPlaces, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import s from "../places.module.css";

type Props = { params: Promise<{ id: string }> };

export function generateStaticParams() {
  return listPlaces().map((p) => ({ id: p.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: getPlace(id)?.name ?? "地点档案" };
}

/**
 * 一个景点的详情：普通网页版。
 * 四个主题（景点概览、游玩建议、景点图册、周边美食）是同一页上的四张信纸，上沿的索引用锚点跳转，
 * 所以 /places/yellow-crane-tower#tips 这样的地址可以直接分享。
 * 数据里没有的条目显示手写的"待补充"，不编内容。
 */
export default async function Page({ params }: Props) {
  const { id } = await params;
  const place = getPlace(id);
  if (!place) notFound();

  const all = listPlaces();
  const no = frameNo(place.id);
  const prev = all[no - 2];
  const next = all[no];

  return (
    <Scene
      scene={SCENES.place}
      count={`第 ${pad2(no)} 张 / 共 ${pad2(all.length)} 张${IS_SAMPLE ? " · 示例数据" : ""}`}
      title={place.name}
      kicker={place.district}
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

        <div className={s.sheets}>
          {THEMES.map((theme, i) => (
            <Paper key={theme.id} id={theme.id} as="section" className={s.sheet} tilt={i % 2 ? 0.5 : -0.5} aria-label={theme.name}>
              <PaperMark>
                {place.name} · {pad2(i + 1)} / {pad2(THEMES.length)}
              </PaperMark>
              <PaperTitle>{theme.name}</PaperTitle>
              <Rule />
              <dl className={s.entries}>
                {theme.fields.map((f) => (
                  <div key={f.key}>
                    <dt>{f.label}</dt>
                    <dd>{place.fields[f.key] ?? <PencilNote>待补充</PencilNote>}</dd>
                  </div>
                ))}
              </dl>
              <div className={s.sheetFoot}>
                <div>
                  <p>来源：{place.source ?? "待补充"}</p>
                  <p>核实日期：{place.verifiedAt ?? "待补充"}</p>
                </div>
                <Stamp status={place.status} />
              </div>
            </Paper>
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
