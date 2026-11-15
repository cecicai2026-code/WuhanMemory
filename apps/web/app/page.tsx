import { Scene } from "@/components/shell/Scene";
import { StageProvider, StageToggle } from "@/components/stage/StageProvider";
import { Label, Paper, PaperMark, PaperTitle, Title } from "@/components/ui";
import { SCENES } from "@/lib/scenes";
import { DeskStage, type DeskStop } from "./DeskStage";
import s from "./home.module.css";

/**
 * 首页。普通版是标题加四个入口；立体版（板块 1B，设计规范第 9.4 节）是桌面全景，
 * 镜头依次停在胶卷罐、灯箱、两台打字机、笔记本上，四个入口的文字和普通版是同一份（下面的 STOPS）。
 * 文案用样片的草稿，Cecilia 2026-11-15 确认（设计规范第 15 节第 8 条）。
 */
const STOPS: DeskStop[] = [
  {
    scene: SCENES.places,
    object: "胶卷罐",
    title: "一卷胶片，一座城",
    text: "在看片器里一格一格看景点。点开一格，把它晾起来，再读它的概览、游玩建议、图册和周边美食。",
    action: "打开胶卷"
  },
  {
    scene: SCENES.map,
    object: "灯箱和地图",
    title: "说出来，画在地图上",
    text: "用日常的话说你想怎么玩。AI 生成逐日行程，用景点数据校验通过之后，才画到可以切换 2D 和 3D 的地图上。",
    action: "点亮灯箱"
  },
  {
    scene: SCENES.compare,
    object: "两台打字机",
    title: "同一个问题，两份回答",
    text: "同一个请求同时交给千问和豆包。两份行程左右并排，中间一张评分卡，上面的指标都是程序算出来的。",
    action: "看两份回答"
  },
  {
    scene: SCENES.trips,
    object: "笔记本",
    title: "夹在本子里的印样",
    text: "生成过的行程都夹在笔记本里。可以再打开，或者生成一个只读的分享链接。",
    action: "翻开笔记本"
  }
];

const TILT = [-1.5, 1, 1.5, -1];

export default function HomePage() {
  return (
    <StageProvider>
      <Scene scene={SCENES.desk} back={null} corner={<StageToggle />}>
        <DeskStage stops={STOPS} />
        <div className={s.hero}>
          <Label>Wuhan Memory · 暗房里的一张木桌</Label>
          <Title className={s.name}>武汉记忆</Title>
          <p className={s.sub}>用一场对话，冲洗出一份画在地图上的武汉行程。</p>
        </div>

        <ul className={s.entries}>
          {STOPS.map((e, i) => (
            <li key={e.scene.path}>
              <Paper kind="card" href={e.scene.path} tilt={TILT[i]} className={s.entry}>
                <PaperMark>
                  物件 {String(i + 1).padStart(2, "0")} · {e.object} → {e.scene.page}
                </PaperMark>
                <PaperTitle>{e.title}</PaperTitle>
                <p>{e.text}</p>
              </Paper>
            </li>
          ))}
        </ul>
      </Scene>
    </StageProvider>
  );
}
