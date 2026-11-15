import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { Paper, PaperMark, PaperTitle, PencilNote, Soft, Stamp, TextLink } from "@/components/ui";
import { formatDate } from "@/lib/format-poi";
import { ApiUnavailableError, listDistricts, listPlaces, pad2, photoUrl } from "@/lib/places";
import type { PoiList } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { ApiDown } from "./PlaceParts";
import s from "./places.module.css";

export const metadata: Metadata = { title: "地点档案" };
// 状态和日期有关，每次请求现取
export const dynamic = "force-dynamic";

const TILT = [-1.2, 0.8, 1.4, -0.8, 1, -1.4];

/**
 * 地点档案的列表：普通网页版，数据来自 GET /api/pois。
 * 立体的胶卷幕在板块 1B 做；这一版以后留作手机端、无障碍和立体场景加载失败时的版本。
 * 区域筛选写在地址里（/places?district=武昌区），刷新或分享链接后看到的是同一个结果。
 */
export default async function Page({ searchParams }: { searchParams: Promise<{ district?: string | string[] }> }) {
  const params = await searchParams;

  let data: PoiList;
  try {
    data = await listPlaces();
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.places} title="地点档案" kicker="胶卷">
        <ApiDown message={err.message} />
      </Scene>
    );
  }

  const all = data.pois;
  const districts = listDistricts(all);
  const asked = typeof params.district === "string" ? params.district : undefined;
  // 地址里的区不存在时，当作没有筛选
  const district = districts.some((d) => d.name === asked) ? asked : undefined;
  const shown = district ? all.filter((p) => p.district === district) : all;

  return (
    <Scene
      scene={SCENES.places}
      count={`共 ${pad2(all.length)} 格`}
      title="地点档案"
      kicker="胶卷"
      intro={all.length ? `每张卡上的章按 ${formatDate(data.asOf)} 的日期计算。` : undefined}
    >
      {all.length === 0 ? (
        <Paper className={s.notice}>
          <PaperTitle level={3}>还没有景点资料</PaperTitle>
          <p>景点资料放在 data/pois/ 里，每个景点一个文件。录入并通过数据检查后，景点会出现在这里。</p>
        </Paper>
      ) : (
        <>
          <nav className={s.filter} aria-label="按区域筛选">
            <TextLink href="/places" current={!district}>
              全部 {all.length}
            </TextLink>
            {districts.map((d) => (
              <TextLink key={d.name} href={`/places?district=${encodeURIComponent(d.name)}`} current={district === d.name}>
                {d.name} {d.count}
              </TextLink>
            ))}
          </nav>

          <ul className={s.grid}>
            {shown.map((p, i) => {
              const no = all.indexOf(p) + 1;
              const cover = p.coverPhoto;
              const src = photoUrl(cover?.url ?? null);
              const { pending, missing, expired } = p.counts;
              return (
                <li key={p.id}>
                  <Paper kind="card" href={`/places/${p.id}`} tilt={TILT[i % TILT.length]} className={s.card}>
                    <span className={s.frame}>
                      <span className={s.frameNo}>{pad2(no)}</span>
                      {src && cover ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img className={s.frameImg} src={src} alt={cover.caption} loading="lazy" />
                      ) : (
                        <PencilNote>照片待补充</PencilNote>
                      )}
                      {cover?.placeholder && <span className={s.frameTag}>占位</span>}
                    </span>
                    <PaperMark>第 {pad2(no)} 格</PaperMark>
                    <PaperTitle level={3}>{p.name}</PaperTitle>
                    <span className={s.foot}>
                      <Soft>{p.district}</Soft>
                      <Stamp status={p.status} />
                    </span>
                    {(pending > 0 || missing > 0 || expired > 0) && (
                      <span className={s.cardCounts}>
                        {[expired && `已过期 ${expired}`, pending && `待确认 ${pending}`, missing && `待补充 ${missing}`]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    )}
                  </Paper>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Scene>
  );
}
