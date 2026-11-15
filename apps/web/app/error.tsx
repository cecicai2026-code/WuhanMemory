"use client";

import { useEffect } from "react";
import { useT } from "@/components/i18n/LangProvider";
import { Scene } from "@/components/shell/Scene";
import { SCENES } from "@/lib/scenes";
import { BrassButton, Paper, PaperMark, PaperTitle, Rule, Soft } from "@/components/ui";
import s from "@/components/shell/blank.module.css";

/**
 * 页面代码出了没预料到的错时显示（后端连不上之类预料到的情况，各页面自己有说明）。
 * 不把错误原文给访客看；开发时原文在浏览器控制台和终端里。
 */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const t = useT();
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <Scene scene={SCENES.desk} title={t("这一页出错了", "Something went wrong")} kicker={t("出错", "Error")}>
      <Paper as="section" className={s.sheet} tilt={-1}>
        <PaperMark>{t("出错", "Error")}</PaperMark>
        <PaperTitle>{t("这一页没能显示出来", "This page couldn't be shown")}</PaperTitle>
        <Rule />
        <p>
          {t(
            "网站自己的程序出了问题，不是你操作错了。可以再试一次；还不行的话，用左下角回到桌面，换一个页面。",
            "Something went wrong in the site's own code, not in anything you did. You can try again; if that doesn't work, go back to the desk (bottom left) and pick another page."
          )}
        </p>
        {error.digest ? <Soft>{t("错误编号", "Error ID")} {error.digest}</Soft> : null}
        <Rule dashed />
        <p>
          <BrassButton onClick={reset}>{t("再试一次", "Try again")}</BrassButton>
        </p>
      </Paper>
    </Scene>
  );
}
