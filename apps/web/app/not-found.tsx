import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { Paper, PaperMark, PaperTitle, Rule, TextLink } from "@/components/ui";
import s from "@/components/shell/blank.module.css";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getT();
  return { title: t("找不到这一页", "Page not found") };
}

/** 网址打错、景点或行程不存在时显示（Next.js 的 notFound() 也到这里） */
export default async function NotFound() {
  const t = await getT();
  return (
    <Scene scene={SCENES.desk} title={t("找不到这一页", "Page not found")} kicker="404">
      <Paper as="section" className={s.sheet} tilt={-1}>
        <PaperMark>{t("桌上没有这张纸", "No such sheet on the desk")}</PaperMark>
        <PaperTitle>{t("这个网址没有对应的页面", "There is no page at this address")}</PaperTitle>
        <Rule />
        <p>
          {t(
            "可能是网址抄错了，或者这个景点、这份行程不存在。可以从下面这几处重新开始：",
            "The address may have been copied wrong, or this place or trip doesn't exist. You can start again from one of these:"
          )}
        </p>
        <p>
          <TextLink href="/map" onPaper>
            {t("地图工作台", "Map Workbench")} →
          </TextLink>{" "}
          <TextLink href="/places" onPaper>
            {t("地点档案", "Places")} →
          </TextLink>{" "}
          <TextLink href="/trips" onPaper>
            {t("我的行程", "My Trips")} →
          </TextLink>
        </p>
      </Paper>
    </Scene>
  );
}
