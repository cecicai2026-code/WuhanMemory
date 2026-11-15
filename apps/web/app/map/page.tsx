import type { Metadata } from "next";
import type { PoiSummary } from "@wuhanmemory/shared";
import { Scene } from "@/components/shell/Scene";
import { ApiUnavailableError, listPlaces } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { Workbench } from "./Workbench";

export const metadata: Metadata = { title: "地图工作台" };

/** 地图工作台：正好占满一屏。这一页自己就是"开始规划"的目的地，所以右下角不放那个按钮。 */
export default async function Page() {
  // 景点从后端取（板块 2 的接口）。后端没开时地图照样显示，只是没有图钉
  let pois: PoiSummary[] = [];
  let poisError: string | null = null;
  try {
    pois = (await listPlaces()).pois;
    if (pois.length === 0) poisError = "后端没有返回景点。运行 corepack pnpm check:data 看看景点资料有没有错误。";
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    poisError = `${err.message}，所以地图上没有景点。先启动后端：corepack pnpm dev:api`;
  }
  return (
    <Scene scene={SCENES.map} showPlan={false} fit>
      <h1 className="sr-only">地图工作台</h1>
      <Workbench pois={pois} poisError={poisError} />
    </Scene>
  );
}
