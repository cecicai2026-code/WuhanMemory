import type { Metadata } from "next";
import { Blank } from "@/components/shell/Blank";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";

export const metadata: Metadata = { title: "地图工作台" };

export default function Page() {
  return (
    <Scene scene={SCENES.map} title="地图工作台" kicker="灯箱">
      <Blank mark="灯箱" when="下一步就做">
        左边是对话，中间是地图，旁边是逐日行程。
      </Blank>
    </Scene>
  );
}
