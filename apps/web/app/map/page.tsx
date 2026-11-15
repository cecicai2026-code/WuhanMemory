import type { Metadata } from "next";
import type { PoiSummary } from "@wuhanmemory/shared";
import { Scene } from "@/components/shell/Scene";
import { ApiUnavailableError, listPlaces } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { PlannerCorner, PlannerStateProvider } from "./PlannerState";
import { Workbench } from "./Workbench";
import { getLang } from "@/lib/i18n-server";
import { makeT } from "@/lib/i18n";

export async function generateMetadata(): Promise<Metadata> {
  const t = makeT(await getLang());
  return { title: t("地图工作台", "Map Workbench") };
}

/** 地图工作台：正好占满一屏。这一页自己就是"开始规划"的目的地，所以右下角不放那个按钮。
 * 右上角的标注是当前模型和当前行程的校验结果（设计规范第 7 节）。 */
export default async function Page() {
  const lang = await getLang();
  const t = makeT(lang);
  // 景点从后端取（板块 2 的接口）。后端没开时地图照样显示，只是没有图钉
  let pois: PoiSummary[] = [];
  let poisError: string | null = null;
  try {
    pois = (await listPlaces(lang)).pois;
    if (pois.length === 0) poisError = t(
        "后端没有返回景点。运行 corepack pnpm check:data 看看景点资料有没有错误。",
        "The backend returned no places. Run corepack pnpm check:data to check the place data for errors."
      );
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    poisError =
      process.env.NODE_ENV === "development"
        ? t(`${err.message}，所以地图上没有景点。先启动后端：corepack pnpm dev:api`, `${err.message}, so there are no places on the map. Start the backend first: corepack pnpm dev:api`)
        : t("网站的后台暂时连不上，所以地图上没有景点。请稍后刷新。", "The site's backend can't be reached right now, so there are no places on the map. Please refresh later.");
  }
  return (
    <PlannerStateProvider>
      <Scene scene={SCENES.map} showPlan={false} fit count={<PlannerCorner />}>
        <h1 className="sr-only">{t("地图工作台", "Map Workbench")}</h1>
        <Workbench pois={pois} poisError={poisError} />
      </Scene>
    </PlannerStateProvider>
  );
}
