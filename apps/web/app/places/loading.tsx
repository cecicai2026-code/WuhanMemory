import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function PlacesLoading() {
  const t = await getT();
  return <Loading scene={SCENES.places} title={t("地点档案", "Places")} text={t("正在取景点资料……", "Fetching the places…")} />;
}
