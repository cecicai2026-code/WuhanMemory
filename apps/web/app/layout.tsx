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
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
