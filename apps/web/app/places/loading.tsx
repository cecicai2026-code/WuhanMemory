import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function PlacesLoading() {
  return <Loading scene={SCENES.places} title="地点档案" text="正在取景点资料……" />;
}
