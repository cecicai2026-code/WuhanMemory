import type { Metadata } from "next";
import { LangProvider } from "@/components/i18n/LangProvider";
import { htmlLang } from "@/lib/i18n";
import { getLang } from "@/lib/i18n-server";

// 字体都装在项目里（OFL 开源许可），不依赖国外的字体服务。中文字体按字集拆成小文件，用到哪些字才下载哪些。
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/cormorant-garamond/500-italic.css";
import "@fontsource/courier-prime/400.css";
import "@fontsource/courier-prime/700.css";
import "@fontsource/caveat/500.css";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/noto-serif-sc/600.css";
import "lxgw-wenkai-webfont/lxgwwenkai-regular.css";
import "lxgw-wenkai-webfont/lxgwwenkai-bold.css";
import "./globals.css";
import { PRECHECK_SCRIPT } from "@/lib/scene3d/precheck";

export async function generateMetadata(): Promise<Metadata> {
  const en = (await getLang()) === "en";
  return {
    title: {
      default: en ? "Wuhan Memory" : "武汉记忆 WuhanMemory",
      template: en ? "%s · Wuhan Memory" : "%s · 武汉记忆"
    },
    description: en ? "Plan a Wuhan trip by talking it through, drawn on a map." : "用对话规划武汉行程，画在地图上。"
  };
}

export default async function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const lang = await getLang();
  return (
    // data-stage 由 <head> 里的脚本在 React 接手前设好（立体场景的暗幕），所以 <html> 的属性可能和服务器输出的不一样
    <html lang={htmlLang(lang)} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: PRECHECK_SCRIPT }} />
      </head>
      <body>
        <LangProvider initial={lang}>{children}</LangProvider>
      </body>
    </html>
  );
}
