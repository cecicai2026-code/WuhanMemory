"use client";

import { useEffect } from "react";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { BrassButton, Paper, PaperMark, PaperTitle, Rule, Soft } from "@/components/ui";
import s from "@/components/shell/blank.module.css";

/**
 * 页面代码出了没预料到的错时显示（后端连不上之类预料到的情况，各页面自己有说明）。
 * 不把错误原文给访客看；开发时原文在浏览器控制台和终端里。
 */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <Scene scene={SCENES.desk} title="这一页出错了" kicker="出错">
      <Paper as="section" className={s.sheet} tilt={-1}>
        <PaperMark>出错</PaperMark>
        <PaperTitle>这一页没能显示出来</PaperTitle>
        <Rule />
        <p>网站自己的程序出了问题，不是你操作错了。可以再试一次；还不行的话，用左下角回到桌面，换一个页面。</p>
        {error.digest ? <Soft>错误编号 {error.digest}</Soft> : null}
        <Rule dashed />
        <p>
          <BrassButton onClick={reset}>再试一次</BrassButton>
        </p>
      </Paper>
    </Scene>
  );
}
