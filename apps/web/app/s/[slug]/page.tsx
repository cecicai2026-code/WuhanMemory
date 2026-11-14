import type { Metadata } from "next";
import { Blank } from "@/components/shell/Blank";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";

export const metadata: Metadata = { title: "分享的行程" };

/** 分享页。旧的 mock 版本已删除，真正的分享页在板块 7 做。 */
export default function SharePage() {
  return (
    <Scene scene={SCENES.share} title="分享的行程" kicker="只读">
      <Blank mark="明信片" when="板块 7 来做">
        每份行程会有一个固定链接，打开后是只读的地图、逐日行程和景点信息。
      </Blank>
    </Scene>
  );
}
