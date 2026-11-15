import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function TripLoading() {
  const t = await getT();
  return <Loading scene={SCENES.trips} title={t("我的行程", "My Trips")} text={t("正在取这份行程……", "Fetching this trip…")} />;
}
