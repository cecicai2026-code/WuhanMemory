import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { TripsNotebook } from "./TripsNotebook";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getT();
  return { title: t("我的行程", "My Trips") };
}

/** 我的行程（板块 7）。没有登录：列的是这台电脑上数据库里的全部行程。 */
export default async function Page() {
  const t = await getT();
  return (
    <Scene
      scene={SCENES.trips}
      title={t("我的行程", "My Trips")}
      kicker={t("夹在本子里的印样", "Proofs tucked into a notebook")}
      intro={t(
        "地图工作台上排过的行程都在这里，每次修改是一个新版本。分享链接指向某一个版本，原行程以后再改也不影响它。",
        "Every trip planned on the map workbench is kept here, and each change is a new version. A share link points to one version, so later edits to the trip don't change it."
      )}
    >
      <TripsNotebook />
    </Scene>
  );
}
