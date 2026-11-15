import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Paper, PaperMark, PaperTitle } from "@/components/ui";
import { Scene } from "@/components/shell/Scene";
import { ShareControls } from "@/components/trip/ShareControls";
import { TripView } from "@/components/trip/TripView";
import { ApiUnavailableError } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { getActiveShareOnServer, getVersionOnServer } from "@/lib/share";

type Props = { params: Promise<{ versionId: string }> };

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "我的行程" };

/** 我的行程里打开的一个版本：和分享页一样的只读视图，明信片上多了分享按钮。 */
export default async function Page({ params }: Props) {
  const { versionId } = await params;
  const back = { href: "/trips", label: "回到我的行程" };
  let got;
  try {
    const [version, share] = await Promise.all([getVersionOnServer(versionId), getActiveShareOnServer(versionId)]);
    got = { version, share };
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return (
      <Scene scene={SCENES.trips} title="我的行程" kicker="一条印样" back={back}>
        <Paper as="section">
          <PaperMark>笔记本</PaperMark>
          <PaperTitle>行程暂时取不到</PaperTitle>
          {process.env.NODE_ENV === "development" ? (
            <>
              <p>{err.message}。行程由后端提供，请先启动后端再刷新：</p>
              <pre>cd ~/WuhanMemory-project2 && corepack pnpm dev:api</pre>
            </>
          ) : (
            <p>网站的后台暂时连不上，请稍后刷新。</p>
          )}
        </Paper>
      </Scene>
    );
  }
  if (!got.version) notFound();
  const v = got.version;

  return (
    <Scene scene={SCENES.trips} title="我的行程" kicker="一条印样" back={back}>
      <TripView
        version={v}
        mark={`我的行程 · 第 ${v.versionNumber} 版`}
        note="这是保存下来的一个版本，不会再变。生成的分享链接也指向这一版。"
        actions={<ShareControls versionId={v.id} failed={v.validation.status === "failed"} initial={got.share} />}
      />
    </Scene>
  );
}
