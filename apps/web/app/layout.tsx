import type { Metadata } from "next";

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

export const metadata: Metadata = {
  title: {
    default: "武汉记忆 WuhanMemory",
    template: "%s · 武汉记忆"
  },
  description: "用对话规划武汉行程，画在地图上。"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // data-stage 由 <head> 里的脚本在 React 接手前设好（立体场景的暗幕），所以 <html> 的属性可能和服务器输出的不一样
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: PRECHECK_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
