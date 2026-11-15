import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function PlaceLoading() {
  const t = await getT();
  return <Loading scene={SCENES.place} text={t("正在取这个景点的资料……", "Fetching this place…")} />;
}
