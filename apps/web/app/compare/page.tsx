import type { Metadata } from "next";
import { Blank } from "@/components/shell/Blank";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";

export const metadata: Metadata = { title: "模型对比" };

export default function Page() {
  return (
    <Scene scene={SCENES.compare} title="模型对比" kicker="同一个请求 · 两个模型">
      <Blank mark="评分卡" when="板块 6 来做">
        同一个请求同时交给千问和豆包，两份行程左右并排，中间一张评分卡。卡上的指标全部由程序算出来。
      </Blank>
    </Scene>
  );
}
