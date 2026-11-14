import { Scene } from "@/components/shell/Scene";
import { Label, Paper, PaperMark, PaperTitle, Title } from "@/components/ui";
import { SCENES } from "@/lib/scenes";
import s from "./home.module.css";

/**
 * 首页的普通网页版：标题加四个入口。
 * 桌面全景的立体场景在板块 1B 做，这一版以后留作手机端和无障碍的版本。
 * 文案是草稿，由 Cecilia 定稿。
 */
const ENTRIES = [
  {
    scene: SCENES.map,
    title: "地图工作台",
    text: "用日常的话说你想怎么玩，行程画在地图上。"
  },
  {
    scene: SCENES.places,
    title: "地点档案",
    text: "一个一个看景点：概览、游玩建议、图册、周边美食。"
  },
  {
    scene: SCENES.compare,
    title: "模型对比",
    text: "同一个请求交给千问和豆包，两份行程并排看。"
  },
  {
    scene: SCENES.trips,
    title: "我的行程",
    text: "生成过的行程都收在这里。"
  }
];

const TILT = [-1.5, 1, 1.5, -1];

export default function HomePage() {
  return (
    <Scene scene={SCENES.desk} back={null}>
      <div className={s.hero}>
        <Label>Wuhan Memory · 暗房里的一张木桌</Label>
        <Title className={s.name}>武汉记忆</Title>
        <p className={s.sub}>用一场对话，排出一份画在地图上的武汉行程。</p>
      </div>

      <ul className={s.entries}>
        {ENTRIES.map((e, i) => (
          <li key={e.scene.path}>
            <Paper kind="card" href={e.scene.path} tilt={TILT[i]} className={s.entry}>
              <PaperMark>
                {e.scene.no} · {e.scene.name}
              </PaperMark>
              <PaperTitle>{e.title}</PaperTitle>
              <p>{e.text}</p>
            </Paper>
          </li>
        ))}
      </ul>
    </Scene>
  );
}
