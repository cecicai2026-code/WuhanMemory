import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Paper, PaperMark, PaperTitle, Rule } from "@/components/ui";
import { Scene } from "@/components/shell/Scene";
import { TripView } from "@/components/trip/TripView";
import { cityDate } from "@/lib/dates";
import { ApiUnavailableError } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { getSharePage, type ShareResult } from "@/lib/share";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

async function load(slug: string): Promise<ShareResult | { kind: "down"; message: string }> {
  try {
    return await getSharePage(slug);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return { kind: "down", message: err.message };
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const got = await load(slug);
  // 分享页只给拿到链接的人看，不让搜索引擎收录
  const robots = { index: false, follow: false };
  return { title: got.kind === "ok" ? got.page.version.title : "分享的行程", robots };
}

function Notice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper as="section" tilt={-1}>
      <PaperMark>明信片</PaperMark>
      <PaperTitle>{title}</PaperTitle>
      <Rule />
      {children}
    </Paper>
  );
}

/**
 * 分享页（板块 7）：只读。链接绑定一个行程版本（不可变快照），原行程以后再改也不影响这一页。
 * 内容和 /map 的行程卡一样：地图、逐日行程、每站的景点资料（带核实状态）、校验结果、所用模型。
 */
export default async function SharePage({ params }: Props) {
  const { slug } = await params;
  const got = await load(slug);

  if (got.kind !== "ok") {
    return (
      <Scene scene={SCENES.share} title="分享的行程" kicker="只读">
        {got.kind === "revoked" && (
          <Notice title="这个链接已经撤回">
            <p>分享这份行程的人撤回了链接，现在看不到了。可以请对方重新分享一次。</p>
          </Notice>
        )}
        {got.kind === "missing" && (
          <Notice title="没有这个分享链接">
            <p>链接可能抄错了，请对照一下原来的网址。</p>
          </Notice>
        )}
        {got.kind === "down" && (
          <Notice title="行程暂时取不到">
            <p>{got.message}。请稍后刷新这一页。</p>
          </Notice>
        )}
      </Scene>
    );
  }

  const { page } = got;
  return (
    <Scene scene={SCENES.share} title="分享的行程" kicker="只读">
      <TripView
        version={page.version}
        mark="明信片 · 只读"
        note={
          <>
            这是 {cityDate(page.createdAt)} 分享时那一版的快照，原行程以后再改也不会变。景点资料多数是占位，还没实地核实，出发前请再确认开放时间和票价。
          </>
        }
      />
    </Scene>
  );
}
