"use client";

import { useId, useState, type FormEvent } from "react";
import { BrassButton, LineInput, Soft } from "@/components/ui";
import { setOwnerPasscode } from "@/lib/owner-passcode";
import s from "./trip.module.css";

/**
 * 公开模式下，我的行程和分享管理要网站主人的口令（板块 7）。
 * 口令只存在这台电脑的浏览器里；输错了后端会再要一次。
 */
export function OwnerPasscodeForm({ onSaved, wrong }: { onSaved: () => void; wrong?: boolean }) {
  const id = useId();
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setOwnerPasscode(value.trim());
    setValue("");
    onSaved();
  }

  return (
    <form className={s.passcode} onSubmit={submit}>
      <p>这个功能只给网站主人用。{wrong ? "口令不对，请再输一次。" : "请输入口令。"}</p>
      <LineInput id={id} label="口令" type="password" autoComplete="current-password" value={value} onChange={(e) => setValue(e.target.value)} />
      <BrassButton type="submit">确定</BrassButton>
      <Soft>口令只存在这台电脑的浏览器里。</Soft>
    </form>
  );
}
