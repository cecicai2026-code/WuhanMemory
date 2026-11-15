import { Loading } from "@/components/shell/Loading";
import { SCENES } from "@/lib/scenes";

export default function SheetLoading() {
  return <Loading scene={SCENES.sheet} text="正在取这张纸的资料……" />;
}
