import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { TripsNotebook } from "./TripsNotebook";

export const metadata: Metadata = { title: "我的行程" };

/** 我的行程（板块 7）。没有登录：列的是这台电脑上数据库里的全部行程。 */
export default function Page() {
  return (
    <Scene
      scene={SCENES.trips}
      title="我的行程"
      kicker="夹在本子里的印样"
      intro="地图工作台上排过的行程都在这里，每次修改是一个新版本。分享链接指向某一个版本，原行程以后再改也不影响它。"
    >
      <TripsNotebook />
    </Scene>
  );
}
