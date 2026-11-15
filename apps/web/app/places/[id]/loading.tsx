import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function PlaceLoading() {
  return <Loading scene={SCENES.place} text="正在取这个景点的资料……" />;
}
