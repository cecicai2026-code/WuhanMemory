import { Scene } from "@/components/shell/Scene";
import { StageProvider, StageToggle } from "@/components/stage/StageProvider";
import { Label, Paper, PaperMark, PaperTitle, Title } from "@/components/ui";
import { SCENES } from "@/lib/scenes";
import type { T } from "@/lib/i18n";
import { getT } from "@/lib/i18n-server";
import { DeskStage, type DeskStop } from "./DeskStage";
import s from "./home.module.css";

/**
 * 首页。普通版是标题加四个入口；立体版（板块 1B，设计规范第 9.4 节）是桌面全景，
 * 镜头依次停在胶卷罐、灯箱、两台打字机、笔记本上，四个入口的文字和普通版是同一份（下面的 STOPS）。
 * 文案用样片的草稿，Cecilia 2026-11-15 确认（设计规范第 15 节第 8 条）。
 */
const stopsFor = (t: T): DeskStop[] => [
  {
    scene: SCENES.places,
    object: t("胶卷罐", "Film canister"),
    title: t("一卷胶片，一座城", "One roll of film, one city"),
    text: t(
      "在看片器里一格一格看景点。点开一格，把它晾起来，再读它的概览、游玩建议、图册和周边美食。",
      "Look through the places frame by frame on the light viewer. Open a frame, hang it up to dry, then read its overview, tips, photos and food nearby."
    ),
    action: t("打开胶卷", "Open the film")
  },
  {
    scene: SCENES.map,
    object: t("灯箱和地图", "Light box and map"),
    title: t("说出来，画在地图上", "Say it, and see it on the map"),
    text: t(
      "用日常的话说你想怎么玩。AI 生成逐日行程，用景点数据校验通过之后，才画到可以切换 2D 和 3D 的地图上。",
      "Describe the trip you want in everyday words. The AI drafts a day-by-day plan, and only after it passes checks against the place data is it drawn on a map you can switch between 2D and 3D."
    ),
    action: t("点亮灯箱", "Light up the box")
  },
  {
    scene: SCENES.compare,
    object: t("两台打字机", "Two typewriters"),
    title: t("同一个问题，两份回答", "One question, two answers"),
    text: t(
      "同一个请求同时交给千问和豆包。两份行程左右并排，中间一张评分卡，上面的指标都是程序算出来的。",
      "The same request goes to Qwen and Doubao at once. The two trips sit side by side with a scorecard between them, and every number on it is computed by the program."
    ),
    action: t("看两份回答", "See both answers")
  },
  {
    scene: SCENES.trips,
    object: t("笔记本", "Notebook"),
    title: t("夹在本子里的印样", "Proofs tucked into a notebook"),
    text: t(
      "生成过的行程都夹在笔记本里。可以再打开，或者生成一个只读的分享链接。",
      "Every trip you've planned is tucked into the notebook. Open one again, or make a read-only share link."
    ),
    action: t("翻开笔记本", "Open the notebook")
  }
];

const TILT = [-1.5, 1, 1.5, -1];

export default async function HomePage() {
  const t = await getT();
  const STOPS = stopsFor(t);
  return (
    <StageProvider>
      <Scene scene={SCENES.desk} back={null} corner={<StageToggle />}>
        <DeskStage stops={STOPS} />
        <div className={s.hero}>
          <Label>{t("Wuhan Memory · 暗房里的一张木桌", "Wuhan Memory · A wooden desk in a darkroom")}</Label>
          <Title className={s.name}>{t("武汉记忆", "Wuhan Memory")}</Title>
          <p className={s.sub}>{t("用一场对话，冲洗出一份画在地图上的武汉行程。", "One conversation, developed into a Wuhan trip drawn on a map.")}</p>
        </div>

        <ul className={s.entries}>
          {STOPS.map((e, i) => (
            <li key={e.scene.path}>
              <Paper kind="card" href={e.scene.path} tilt={TILT[i]} className={s.entry}>
                <PaperMark>
                  {t("物件", "Object")} {String(i + 1).padStart(2, "0")} · {e.object} → {t(e.scene.page, e.scene.en.page)}
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
