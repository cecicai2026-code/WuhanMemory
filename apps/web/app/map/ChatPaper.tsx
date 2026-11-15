"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ConversationMessage, PlanningJob } from "@wuhanmemory/shared";
import { BrassButton, LineInput, Paper, PaperMark, PaperTitle, PencilNote, Rule } from "@/components/ui";
import { ApiError, createConversation, getConversation, getJob, sendMessage } from "@/lib/planning-client";
import { ModelPicker } from "./ModelPicker";
import { usePlannerState } from "./PlannerState";
import s from "./map.module.css";

/** 这段对话的 id 记在浏览器里，刷新页面后接着显示。只是个方便，对话本身存在后端 */
const STORAGE_KEY = "wuhanmemory.conversation";
/** 规划进度：每秒问一次后端（2026-11-15 Cecilia 选的轮询） */
const POLL_MS = 1000;

type Line = Pick<ConversationMessage, "role" | "content" | "kind" | "provider"> & { key: string };

function stored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function store(id: string | null) {
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 存不了不影响使用，只是刷新后对话不在了
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface Props {
  /** 回复带出了一轮方案（板块 5B），或者一个行程版本（板块 5 存的旧回复） */
  onResult: (result: PlanResult) => void;
  /** 开了新对话：清掉右边的行程 */
  onReset: () => void;
}

/**
 * 左边的打字纸：AI 对话（设计规范 9.1）。
 * 用户的话发给后端，带上选中的模型；后端交给规划链路，这里每秒问一次进行到哪一步，
 * 只显示后端真的走过的步骤，不预先画出没发生的步骤。
 */
/** 一条回复带出的结果：新的回复是一轮方案；板块 5 存的旧回复只有一个版本 */
export type PlanResult = { roundId: string } | { versionId: string };

function resultOf(m: { planningRoundId?: string | null; itineraryVersionId: string | null }): PlanResult | null {
  if (m.planningRoundId) return { roundId: m.planningRoundId };
  if (m.itineraryVersionId) return { versionId: m.itineraryVersionId };
  return null;
}

export function ChatPaper({ onResult, onReset }: Props) {
  const { provider, setProvider } = usePlannerState();
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [draft, setDraft] = useState("");
  const [job, setJob] = useState<PlanningJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [problem, setProblem] = useState<string | null>(null);
  // 最后一条是用户的话、却没有回复，后端也没有在跑的任务：多半是规划中途后端重启了
  const [orphan, setOrphan] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  // 打开页面时接着上次的对话
  useEffect(() => {
    const id = stored();
    if (!id) return;
    let closed = false;
    getConversation(id)
      .then((conv) => {
        if (closed) return;
        setConversationId(conv.conversationId);
        setLines(conv.messages.map((m) => ({ ...m, key: `m${m.id}` })));
        const last = [...conv.messages].reverse().map(resultOf).find((r) => r !== null);
        if (last) onResult(last);
        if (conv.runningJobId) {
          // 刷新前发的那条还在规划中：接着显示进度
          setStartedAt(Date.now());
          setElapsed(0);
          void follow(conv.runningJobId);
        } else if (conv.messages.at(-1)?.role === "user") {
          setOrphan(true);
        }
      })
      .catch((err: unknown) => {
        // 后端换了数据库等情况下找不到这段对话：当作新对话
        if (err instanceof ApiError && err.status === 404) store(null);
      });
    return () => {
      closed = true;
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [lines, job]);

  useEffect(() => {
    if (startedAt === null) return;
    const t = window.setInterval(() => setElapsed(Math.round((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(t);
  }, [startedAt]);

  function add(line: Omit<Line, "key">) {
    setLines((cur) => [...cur, { ...line, key: `l${Date.now()}-${cur.length}` }]);
  }

  /** 跟着一个规划任务，直到它完成或出错。发消息后、刷新页面发现还有任务在跑时都用它 */
  async function follow(jobId: string) {
    setBusy(true);
    try {
      let current = await getJob(jobId);
      setJob(current);
      while (current.status === "queued" || current.status === "running") {
        await sleep(POLL_MS);
        current = await getJob(jobId);
        setJob(current);
      }
      if (current.status === "failed") {
        add({ role: "assistant", content: `模型调用出错：${current.error?.message ?? "未知错误"}`, kind: "error", provider: current.error?.provider ?? null });
      } else {
        add({ role: "assistant", content: current.reply ?? "", kind: current.kind, provider: current.provider });
        const result = resultOf(current);
        if (result) onResult(result);
      }
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setJob(null);
      setStartedAt(null);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    setProblem(null);
    setDraft("");
    setOrphan(false);
    add({ role: "user", content: text, kind: null, provider: null });
    setStartedAt(Date.now());
    setElapsed(0);
    let jobId: string;
    try {
      let id = conversationId;
      if (!id) {
        id = (await createConversation()).conversationId;
        setConversationId(id);
        store(id);
      }
      jobId = (await sendMessage(id, text, provider)).planningJobId;
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
      setBusy(false);
      setStartedAt(null);
      return;
    }
    await follow(jobId);
  }

  function restart() {
    store(null);
    setOrphan(false);
    setConversationId(null);
    setLines([]);
    setProblem(null);
    onReset();
  }

  return (
    <Paper className={s.chat}>
      <div className={s.log} ref={logRef} aria-live="polite">
        <PaperMark>打字纸 · 对话</PaperMark>
        {lines.length === 0 ? (
          <>
            <PaperTitle>想怎么玩</PaperTitle>
            <Rule />
            <p>用日常的话说就行：玩几天、哪天去、喜欢什么、走路多不多。例如“武汉两天，喜欢历史和美食，坐地铁”。</p>
          </>
        ) : (
          <ol className={s.lines}>
            {lines.map((l) => (
              <li key={l.key} className={s.line} data-role={l.role} data-kind={l.kind ?? undefined}>
                <p>{l.content}</p>
                {l.role === "assistant" && l.provider && <span className={s.lineWho}>— {labels[l.provider] ?? l.provider}</span>}
              </li>
            ))}
          </ol>
        )}
        {busy && (
          <div className={s.progress} role="status">
            <p className={s.progressHead}>
              规划中 · 已等 {elapsed} 秒{provider && labels[provider] ? ` · ${labels[provider]}` : ""}
            </p>
            <ol className={s.stages}>
              {(job?.stages ?? []).map((st, i, all) => (
                <li key={`${st.id}-${i}`} data-current={i === all.length - 1 || undefined}>
                  <span aria-hidden="true">{i === all.length - 1 ? "…" : "✓"}</span> {st.label}
                </li>
              ))}
              {!job?.stages.length && <li data-current>…发给后端</li>}
            </ol>
          </div>
        )}
        {orphan && !busy && (
          <p className={s.routeError} role="status">
            最后这条没有回复：规划中途后端重启过，这次规划丢了。可以再发一次。
          </p>
        )}
        {problem && (
          <p className={s.routeError} role="alert">
            没发出去：{problem}
          </p>
        )}
      </div>
      <form className={s.ask} onSubmit={submit}>
        <ModelPicker value={provider} onChange={setProvider} disabled={busy} onLoaded={setLabels} />
        <LineInput
          id="ask"
          label="想怎么玩"
          placeholder="武汉两天，喜欢历史和美食，坐地铁"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy}
          autoComplete="off"
        />
        <div className={s.askRow}>
          {lines.length > 0 && !busy ? (
            <button type="button" className={s.restart} onClick={restart}>
              新对话
            </button>
          ) : (
            <PencilNote>{busy ? "规划中" : ""}</PencilNote>
          )}
          <BrassButton type="submit" disabled={busy || !draft.trim() || !provider}>
            发送
          </BrassButton>
        </div>
      </form>
    </Paper>
  );
}
