import type { Metadata } from "next";
import { Blank } from "@/components/shell/Blank";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";

export const metadata: Metadata = { title: "我的行程" };

export default function Page() {
  return (
    <Scene scene={SCENES.trips} title="我的行程" kicker="夹在本子里的印样">
      <Blank mark="笔记本" when="板块 7 来做">
        生成过的行程会收在这里，可以再打开，或者生成一个只读的分享链接。
      </Blank>
    </Scene>
  );
}
