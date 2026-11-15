import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { CompareDesk } from "./CompareDesk";

export const metadata: Metadata = { title: "模型对比" };

export default function Page() {
  return (
    <Scene
      scene={SCENES.compare}
      title="模型对比"
      kicker="同一个请求 · 两个模型"
      intro="同一个请求、同一份偏好、同一份候选景点、同一种侧重，交给千问和豆包各排一份，左右并排。模型定的是去哪几站、什么顺序、每站待多久，钟点由程序按高德的真实交通推出来。中间的评分卡和下面的差异都由程序算。"
    >
      <CompareDesk />
    </Scene>
  );
}
