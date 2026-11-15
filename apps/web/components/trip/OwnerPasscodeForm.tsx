"use client";

import { useId, useState, type FormEvent } from "react";
import { BrassButton, LineInput, Soft } from "@/components/ui";
import { setOwnerPasscode } from "@/lib/owner-passcode";
import { useT } from "@/components/i18n/LangProvider";
import s from "./trip.module.css";

/**
 * 公开模式下，我的行程和分享管理要网站主人的口令（板块 7）。
 * 口令只存在这台电脑的浏览器里；输错了后端会再要一次。
 */
export function OwnerPasscodeForm({ onSaved, wrong }: { onSaved: () => void; wrong?: boolean }) {
  const id = useId();
  const [value, setValue] = useState("");
  const t = useT();

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setOwnerPasscode(value.trim());
    setValue("");
    onSaved();
  }

  return (
    <form className={s.passcode} onSubmit={submit}>
      <p>
        {t("这个功能只给网站主人用。", "This is for the site owner only. ")}
        {wrong ? t("口令不对，请再输一次。", "Wrong passcode, please try again.") : t("请输入口令。", "Please enter the passcode.")}
      </p>
      <LineInput
        id={id}
        label={t("口令", "Passcode")}
        type="password"
        autoComplete="current-password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <BrassButton type="submit">{t("确定", "OK")}</BrassButton>
      <Soft>{t("口令只存在这台电脑的浏览器里。", "The passcode is kept only in this computer's browser.")}</Soft>
    </form>
  );
}
