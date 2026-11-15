import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function TripLoading() {
  return <Loading scene={SCENES.trips} title="我的行程" text="正在取这份行程……" />;
}
