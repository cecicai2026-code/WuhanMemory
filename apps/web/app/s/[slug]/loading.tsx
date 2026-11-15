import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function ShareLoading() {
  const t = await getT();
  return <Loading scene={SCENES.share} title={t("分享的行程", "A shared trip")} text={t("正在取这份行程……", "Fetching this trip…")} />;
}
