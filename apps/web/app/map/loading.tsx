import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function MapLoading() {
  return <Loading scene={SCENES.map} fit text="正在打开地图工作台……" />;
}
