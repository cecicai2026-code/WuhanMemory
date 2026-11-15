import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Paper, PaperMark, PaperTitle, Rule } from "@/components/ui";
import { Scene } from "@/components/shell/Scene";
import { TripView } from "@/components/trip/TripView";
import { cityDate } from "@/lib/dates";
import { ApiUnavailableError } from "@/lib/places";
import { SCENES } from "@/lib/scenes";
import { getSharePage, type ShareResult } from "@/lib/share";
import { getLang } from "@/lib/i18n-server";
import { makeT } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

async function load(slug: string, lang: Lang): Promise<ShareResult | { kind: "down"; message: string }> {
  try {
    return await getSharePage(slug, lang);
  } catch (err) {
    if (!(err instanceof ApiUnavailableError)) throw err;
    return { kind: "down", message: err.message };
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const lang = await getLang();
  const got = await load(slug, lang);
  // 分享页只给拿到链接的人看，不让搜索引擎收录
  const robots = { index: false, follow: false };
  return { title: got.kind === "ok" ? got.page.version.title : makeT(lang)("分享的行程", "A shared trip"), robots };
}

function Notice({ title, mark, children }: { title: string; mark: string; children: ReactNode }) {
  return (
    <Paper as="section" tilt={-1}>
      <PaperMark>{mark}</PaperMark>
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
  const lang = await getLang();
  const t = makeT(lang);
  const got = await load(slug, lang);
  const mark = t("明信片", "Postcard");
  const title = t("分享的行程", "A shared trip");
  const kicker = t("只读", "Read-only");

  if (got.kind !== "ok") {
    return (
      <Scene scene={SCENES.share} title={title} kicker={kicker}>
        {got.kind === "revoked" && (
          <Notice mark={mark} title={t("这个链接已经撤回", "This link has been withdrawn")}>
            <p>
              {t(
                "分享这份行程的人撤回了链接，现在看不到了。可以请对方重新分享一次。",
                "The person who shared this trip withdrew the link, so it can't be viewed now. You can ask them to share it again."
              )}
            </p>
          </Notice>
        )}
        {got.kind === "missing" && (
          <Notice mark={mark} title={t("没有这个分享链接", "There is no such share link")}>
            <p>{t("链接可能抄错了，请对照一下原来的网址。", "The link may have been copied wrong. Please check it against the original address.")}</p>
          </Notice>
        )}
        {got.kind === "down" && (
          <Notice mark={mark} title={t("行程暂时取不到", "The trip can't be fetched right now")}>
            <p>{t(`${got.message}。请稍后刷新这一页。`, `${got.message}. Please refresh this page later.`)}</p>
          </Notice>
        )}
      </Scene>
    );
  }

  const { page } = got;
  return (
    <Scene scene={SCENES.share} title={title} kicker={kicker}>
      <TripView
        version={page.version}
        mark={t("明信片 · 只读", "Postcard · read-only")}
        note={t(
          `这是 ${cityDate(page.createdAt)} 分享时那一版的快照，原行程以后再改也不会变。景点资料多数是占位，还没实地核实，出发前请再确认开放时间和票价。`,
          `This is a snapshot of the version shared on ${cityDate(page.createdAt)}; later edits to the original trip don't change it. Most place info is a placeholder that hasn't been checked on site, so please confirm opening hours and prices before you go.`
        )}
      />
    </Scene>
  );
}
