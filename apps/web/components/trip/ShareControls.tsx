"use client";

import { useEffect, useState } from "react";
import type { ShareLink } from "@wuhanmemory/shared";
import { NoteButton, Soft, TextLink } from "@/components/ui";
import { ApiError, publishShare, revokeShare } from "@/lib/planning-client";
import { OwnerPasscodeForm } from "./OwnerPasscodeForm";
import s from "./trip.module.css";

interface Props {
  versionId: string;
  /** 没通过校验的版本不能分享（后端也会拒绝） */
  failed: boolean;
  initial: ShareLink | null;
  /** 链接变了（生成或撤回）时告诉外面 */
  onChange?: (link: ShareLink | null) => void;
}

/**
 * 分享链接的按钮：生成 → 显示完整网址、复制、打开、撤回。
 * 完整网址按当前网站拼（本机是 localhost:3000，上线后是上线的域名）。
 */
export function ShareControls({ versionId, failed, initial, onChange }: Props) {
  const [link, setLink] = useState<ShareLink | null>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [origin, setOrigin] = useState("");
  // 公开模式下后端要口令：先输口令，再重做刚才那一步
  const [needPasscode, setNeedPasscode] = useState<{ retry: () => void; wrong: boolean } | null>(null);

  useEffect(() => setOrigin(window.location.origin), []);

  if (failed) return <Soft className={s.shareHint}>没通过校验，不能分享</Soft>;

  async function run(action: () => Promise<ShareLink | null>, triedPasscode = false) {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const next = await action();
      setLink(next);
      onChange?.(next);
      setNeedPasscode(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setNeedPasscode({ retry: () => void run(action, true), wrong: triedPasscode });
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  if (needPasscode) return <OwnerPasscodeForm wrong={needPasscode.wrong} onSaved={needPasscode.retry} />;

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setError("没能复制，请手动选中网址复制");
    }
  }

  function revoke(slug: string) {
    if (!window.confirm("撤回后，拿到这个链接的人就打不开了。撤回后再分享会换一个新链接。确定撤回？")) return;
    void run(async () => {
      await revokeShare(slug);
      return null;
    });
  }

  if (!link) {
    return (
      <div className={s.share}>
        <NoteButton onClick={() => void run(() => publishShare(versionId))}>{busy ? "正在生成……" : "生成分享链接"}</NoteButton>
        {error && (
          <span className={s.shareError} role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }

  const url = `${origin}${link.path}`;
  return (
    <div className={s.share}>
      <label className={s.shareUrl}>
        <span className="sr-only">分享链接</span>
        <input readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
      </label>
      <NoteButton onClick={() => void copy(url)}>{copied ? "已复制" : "复制"}</NoteButton>
      <TextLink href={link.path} onPaper>
        打开分享页 →
      </TextLink>
      <NoteButton onClick={() => revoke(link.slug)}>{busy ? "正在撤回……" : "撤回"}</NoteButton>
      <span className="sr-only" role="status">
        {copied ? "链接已复制" : ""}
      </span>
      {error && (
        <span className={s.shareError} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
