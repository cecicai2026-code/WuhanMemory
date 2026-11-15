import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { CompareDesk } from "./CompareDesk";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getT();
  return { title: t("模型对比", "Compare Models") };
}

export default async function Page() {
  const t = await getT();
  return (
    <Scene
      scene={SCENES.compare}
      title={t("模型对比", "Compare Models")}
      kicker={t("同一个请求 · 两个模型", "One request · two models")}
      intro={t(
        "同一个请求、同一份偏好、同一份候选景点、同一种侧重，交给千问和豆包各排一份，左右并排。模型定的是去哪几站、什么顺序、每站待多久，钟点由程序按高德的真实交通推出来。中间的评分卡和下面的差异都由程序算。",
        "The same request, preferences, candidate places and emphasis go to Qwen and Doubao, and each plans its own trip, shown side by side. The model picks the stops, their order and how long to stay; the clock times are worked out by the program from real AMap travel times. The scorecard in the middle and the differences below are all computed by the program."
      )}
    >
      <CompareDesk />
    </Scene>
  );
}
