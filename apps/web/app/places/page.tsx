import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { Paper, PaperMark, PaperTitle, PencilNote, Soft, Stamp, TextLink } from "@/components/ui";
import { IS_SAMPLE, frameNo, listDistricts, listPlaces, pad2 } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import s from "./places.module.css";

export const metadata: Metadata = { title: "地点档案" };

const TILT = [-1.2, 0.8, 1.4, -0.8, 1, -1.4];

/**
 * 地点档案的列表：普通网页版。
 * 立体的胶卷幕在板块 1B 做；这一版以后留作手机端、无障碍和立体场景加载失败时的版本。
 * 区域筛选写在地址里（/places?district=武昌区），刷新或分享链接后看到的是同一个结果。
 */
export default async function Page({ searchParams }: { searchParams: Promise<{ district?: string | string[] }> }) {
  const params = await searchParams;
  const all = listPlaces();
  const districts = listDistricts();
  const asked = typeof params.district === "string" ? params.district : undefined;
  // 地址里的区不存在时，当作没有筛选
  const district = districts.some((d) => d.name === asked) ? asked : undefined;
  const shown = district ? all.filter((p) => p.district === district) : all;

  return (
    <Scene
      scene={SCENES.places}
      count={`共 ${pad2(all.length)} 格${IS_SAMPLE ? " · 示例数据" : ""}`}
      title="地点档案"
      kicker="胶卷"
      intro={IS_SAMPLE ? "现在是示例清单：只有景点名和所在区，其余资料在板块 2 补上。" : undefined}
    >
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
        {shown.map((p, i) => (
          <li key={p.id}>
            <Paper kind="card" href={`/places/${p.id}`} tilt={TILT[i % TILT.length]} className={s.card}>
              <span className={s.frame}>
                <span className={s.frameNo}>{pad2(frameNo(p.id))}</span>
                <PencilNote>照片待补充</PencilNote>
              </span>
              <PaperMark>第 {pad2(frameNo(p.id))} 格</PaperMark>
              <PaperTitle level={3}>{p.name}</PaperTitle>
              <span className={s.foot}>
                <Soft>{p.district}</Soft>
                <Stamp status={p.status} />
              </span>
            </Paper>
          </li>
        ))}
      </ul>
    </Scene>
  );
}
