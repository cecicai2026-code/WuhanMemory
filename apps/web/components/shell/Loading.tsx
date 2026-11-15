import { Paper, PaperMark, PaperTitle } from "@/components/ui";
import type { SceneInfo } from "@/lib/scenes";
import { Scene } from "./Scene";
import s from "./blank.module.css";

interface Props {
  scene: SceneInfo;
  /** 纸上写在取什么，例如"正在取景点资料……" */
  text: string;
  title?: string;
  fit?: boolean;
}

/**
 * 服务器端取数据时先显示的页面（Next.js 的 loading.tsx 用）：外壳照常，中间一张纸写着在取什么。
 * 后端慢的时候，点了链接马上就有反应，不会像没点上。
 */
export function Loading({ scene, text, title, fit }: Props) {
  return (
    <Scene scene={scene} title={title} fit={fit} showPlan={!fit}>
      <Paper as="section" className={s.sheet} tilt={-1}>
        <PaperMark>请稍等</PaperMark>
        <PaperTitle level={3}>
          <span role="status">{text}</span>
        </PaperTitle>
      </Paper>
    </Scene>
  );
}
