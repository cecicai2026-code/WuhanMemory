import type { ReactNode } from "react";
import { Paper, PaperMark, PaperTitle, PencilNote, Rule } from "@/components/ui";
import s from "./blank.module.css";

interface BlankProps {
  /** 纸左上角的小字 */
  mark: string;
  /** 这一页以后是什么 */
  children: ReactNode;
  /** 在哪个板块做 */
  when: string;
}

/** 还没做的页面：桌上一张空着的信纸，老实写明这里以后放什么、什么时候做。 */
export function Blank({ mark, children, when }: BlankProps) {
  return (
    <Paper as="section" className={s.sheet} tilt={-1}>
      <PaperMark>{mark}</PaperMark>
      <PaperTitle>这一页还空着</PaperTitle>
      <Rule />
      <p>{children}</p>
      <Rule dashed />
      <PencilNote>{when}</PencilNote>
    </Paper>
  );
}
