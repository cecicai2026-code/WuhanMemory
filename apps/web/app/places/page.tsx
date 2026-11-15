import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { Paper, PaperMark, PaperTitle, PencilNote, Soft, Stamp, TextLink } from "@/components/ui";
import { formatDate } from "@/lib/format-poi";
import { ApiUnavailableError, countsText, isClosed, listDistricts, listPlaces, pad2, photoUrl } from "@/lib/places";
import type { PoiList } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { getLang } from "@/lib/i18n-server";
import { makeT } from "@/lib/i18n";
import { StageToggle } from "@/components/stage/StageProvider";
import { rollsFrame } from "@/lib/scene3d/data";
import type { RollsData } from "@/lib/scene3d/data";
import { RollsStage } from "./RollsStage";
import { ApiDown } from "./PlaceParts";
import s from "./places.module.css";

export async function generateMetadata(): Promise<Metadata> {
  return { title: makeT(await getLang())("地点档案", "Places") };
}
// 状态和日期有关，每次请求现取
export const dynamic = "force-dynamic";

const TILT = [-1.2, 0.8, 1.4, -0.8, 1, -1.4];

/**
 * 地点档案的列表：普通网页版，数据来自 GET /api/pois。
 * 立体的胶卷幕在板块 1B 做；这一版以后留作手机端、无障碍和立体场景加载失败时的版本。
 * 区域筛选写在地址里（/places?district=武昌区），刷新或分享链接后看到的是同一个结果。
 */
export default async function Page({ searchParams }: { searchParams: Promise<{ district?: string | string[]; at?: string | string[]; debug?: string | string[] }> }) {
  const params = await searchParams;
  const lang = await getLang();
  const t = makeT(lang);

  let data: PoiList;
  try {
    data = await listPlaces(lang);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.places} title={t("地点档案", "Places")} kicker={t("胶卷", "The film roll")}>
        <ApiDown message={err.message} t={t} />
      </Scene>
    );
  }

  const all = data.pois;
  const districts = listDistricts(all);
  const asked = typeof params.district === "string" ? params.district : undefined;
  // 地址里的区不存在时，当作没有筛选
  const district = districts.some((d) => d.name === asked) ? asked : undefined;
  const shown = district ? all.filter((p) => p.district === district) : all;

  // 立体版（胶卷幕）用的数据：和下面的卡片是同一份
  // 开发时地址带 ?debug=nophoto：假装没有照片，看公开模式下（占位照片不对外）胶卷是什么样子。正式运行时不认
  const noPhoto = process.env.NODE_ENV !== "production" && params.debug === "nophoto";
  const stageData: RollsData = {
    frames: shown.map((p) => rollsFrame(noPhoto ? { ...p, coverPhoto: null } : p, all.indexOf(p) + 1, lang)),
    total: all.length,
    district: district ?? null,
    at: typeof params.at === "string" ? params.at : null,
    lang
  };

  return (
    <Scene
      scene={SCENES.places}
      count={t(`共 ${pad2(all.length)} 格`, `${pad2(all.length)} frames`)}
      title={t("地点档案", "Places")}
      kicker={t("胶卷", "The film roll")}
      intro={all.length ? t(`每张卡上的章按 ${formatDate(data.asOf)} 的日期计算。`, `The stamp on each card is as of ${formatDate(data.asOf)}.`) : undefined}
      corner={<StageToggle />}
    >
      {all.length === 0 ? (
        <Paper className={s.notice}>
          <PaperTitle level={3}>{t("还没有景点资料", "No place data yet")}</PaperTitle>
          <p>
            {t(
              "景点资料放在 data/pois/ 里，每个景点一个文件。录入并通过数据检查后，景点会出现在这里。",
              "Place data lives in data/pois/, one file per place. Once a place is entered and passes the data check, it shows up here."
            )}
          </p>
        </Paper>
      ) : (
        <>
          {shown.length > 0 && <RollsStage data={stageData} stageKey={`rolls:${district ?? "all"}:${lang}`} />}
          <nav className={s.filter} aria-label={t("按区域筛选", "Filter by district")} data-stage-show>
            <TextLink href="/places" current={!district}>
              {t("全部", "All")} {all.length}
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
              // 卡片上的照片不大，用 800 宽的缩略图（板块 1B）
              const src = photoUrl(cover?.url ? (cover.thumbUrl ?? cover.url) : null);
              return (
                <li key={p.id}>
                  <Paper kind="card" href={`/places/${p.id}`} tilt={TILT[i % TILT.length]} className={s.card}>
                    <span className={s.frame}>
                      <span className={s.frameNo}>{pad2(no)}</span>
                      {src && cover ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img className={s.frameImg} src={src} alt={cover.caption} loading="lazy" />
                      ) : (
                        <PencilNote>{t("照片待补充", "Photo to come")}</PencilNote>
                      )}
                      {cover?.placeholder && <span className={s.frameTag}>{t("占位", "Placeholder")}</span>}
                    </span>
                    <PaperMark>{t(`第 ${pad2(no)} 格`, `Frame ${pad2(no)}`)}</PaperMark>
                    <PaperTitle level={3}>{p.name}</PaperTitle>
                    <span className={s.foot}>
                      <Soft>
                        {p.district}
                        {isClosed(p) && t(" · 暂停开放", " · Temporarily closed")}
                      </Soft>
                      <Stamp status={p.status} />
                    </span>
                    {countsText(p.counts, t) && <span className={s.cardCounts}>{countsText(p.counts, t)}</span>}
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
