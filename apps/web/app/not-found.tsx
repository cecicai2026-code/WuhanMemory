import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { Paper, PaperMark, PaperTitle, Rule, TextLink } from "@/components/ui";
import s from "@/components/shell/blank.module.css";

export const metadata: Metadata = { title: "找不到这一页" };

/** 网址打错、景点或行程不存在时显示（Next.js 的 notFound() 也到这里） */
export default function NotFound() {
  return (
    <Scene scene={SCENES.desk} title="找不到这一页" kicker="404">
      <Paper as="section" className={s.sheet} tilt={-1}>
        <PaperMark>桌上没有这张纸</PaperMark>
        <PaperTitle>这个网址没有对应的页面</PaperTitle>
        <Rule />
        <p>可能是网址抄错了，或者这个景点、这份行程不存在。可以从下面这几处重新开始：</p>
        <p>
          <TextLink href="/map" onPaper>
            地图工作台 →
          </TextLink>{" "}
          <TextLink href="/places" onPaper>
            地点档案 →
          </TextLink>{" "}
          <TextLink href="/trips" onPaper>
            我的行程 →
          </TextLink>
        </p>
      </Paper>
    </Scene>
  );
}
