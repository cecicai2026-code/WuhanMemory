import type { ReactNode } from "react";
import { StageProvider } from "@/components/stage/StageProvider";

/**
 * 地点档案的三幕（胶卷、晾片、纸页）共用一个立体场景。放在 layout 里，换页时不卸载，
 * 三幕之间才能做物件飞过去的转场（设计规范 G4）。页面本身照常输出普通版，见 StageProvider 的说明。
 */
export default function PlacesLayout({ children }: { children: ReactNode }) {
  return <StageProvider>{children}</StageProvider>;
}
