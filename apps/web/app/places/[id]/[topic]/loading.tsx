import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";
import { getT } from "@/lib/i18n-server";

export default async function SheetLoading() {
  const t = await getT();
  return <Loading scene={SCENES.sheet} text={t("正在取这张纸的资料……", "Fetching this sheet…")} />;
}
