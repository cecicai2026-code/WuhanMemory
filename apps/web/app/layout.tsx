import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WuhanMemory",
  description: "AI map itinerary planner for Wuhan travel"
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
