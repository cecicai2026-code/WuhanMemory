import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function ShareLoading() {
  return <Loading scene={SCENES.share} title="分享的行程" text="正在取这份行程……" />;
}
