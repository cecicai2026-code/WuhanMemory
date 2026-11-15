import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function MapLoading() {
  const t = await getT();
  return <Loading scene={SCENES.map} fit text={t("正在打开地图工作台……", "Opening the map workbench…")} />;
}
