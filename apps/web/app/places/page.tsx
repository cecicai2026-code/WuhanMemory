import type { Metadata } from "next";
import { Blank } from "@/components/shell/Blank";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";

export const metadata: Metadata = { title: "地点档案" };

export default function Page() {
  return (
    <Scene scene={SCENES.places} title="地点档案" kicker="胶卷">
      <Blank mark="胶卷" when="下一步就做">
        全部景点的列表，可以按区域筛选。
      </Blank>
    </Scene>
  );
}
