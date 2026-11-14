import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { Workbench } from "./Workbench";

export const metadata: Metadata = { title: "地图工作台" };

/** 地图工作台：正好占满一屏。这一页自己就是"开始规划"的目的地，所以右下角不放那个按钮。 */
export default function Page() {
  return (
    <Scene scene={SCENES.map} showPlan={false} fit>
      <h1 className="sr-only">地图工作台</h1>
      <Workbench />
    </Scene>
  );
}
