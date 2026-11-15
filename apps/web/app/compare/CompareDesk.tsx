"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CompareJob,
  Emphasis,
  ItineraryVersion,
  ModelComparison,
  ModelComparisonSummary,
  PlanDiff,
  PoiRef,
  SideResult,
  TravelerPreferences,
} from "@wuhanmemory/shared";
import { BrassButton, NoteButton, Paper, PaperMark, PaperTitle, PencilNote, Rule, Soft, Stamp } from "@/components/ui";
import { ApiError, getCompareJob, getComparison, listComparisons, startComparison } from "@/lib/planning-client";
import s from "./compare.module.css";

const EMPHASES: { id: Emphasis; label: string }[] = [
  { id: "classic", label: "经典必去" },
  { id: "relaxed", label: "轻松少走路" },
  { id: "culture", label: "深度文化" },
];
const PACE = { relaxed: "轻松", moderate: "适中", intensive: "紧凑" } as const;
const PARTY = { solo: "一个人", couple: "两个人", friends: "朋友", family: "家庭", elderly: "带老人" } as const;
const TRANSPORT = { metro: "地铁公交优先", walk: "尽量走路", taxi: "打车" } as const;
const BUDGET = { low: "预算少", medium: "预算中等", high: "预算多" } as const;
const MODE = { walk: "步行", transit: "公交地铁", drive: "打车" } as const;

function prefsText(p: TravelerPreferences): string {
  const parts: string[] = [];
  if (p.days) parts.push(`${p.days} 天`);
  parts.push(p.startDate ? `${p.startDate} 出发` : "日期未定");
  if (p.pace) parts.push(`节奏${PACE[p.pace]}`);
  if (p.party) parts.push(PARTY[p.party]);
  if (p.transport) parts.push(TRANSPORT[p.transport]);
  if (p.budget) parts.push(BUDGET[p.budget]);
  if (p.interests.length) parts.push(`兴趣：${p.interests.join("、")}`);
  if (p.mustVisit.length) parts.push(`必去：${p.mustVisit.join("、")}`);
  if (p.avoid.length) parts.push(`不去：${p.avoid.join("、")}`);
  if (p.notes) parts.push(`其他：${p.notes}`);
  return parts.join(" · ");
}

function when(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}.${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ---------- 一边的打字纸 ----------

function SideStamp({ side }: { side: SideResult }) {
  if (!side.quality) return <Stamp status="expired">没排出来</Stamp>;
  return side.quality.finalPassed ? <Stamp status="verified">通过校验</Stamp> : <Stamp status="expired">未通过</Stamp>;
}

function Sheet({ side, version, only }: { side: SideResult; version: ItineraryVersion | null; only: Set<string> }) {
  const q = side.quality;
  return (
    <Paper as="article" className={s.sheet} aria-label={`${side.providerLabel}排的行程`}>
      <div className={s.bar}>
        <span className={s.barLabel}>{side.providerLabel}</span>
        <span className={s.barModel}>{side.model ?? "模型名不详"}</span>
      </div>
      <div className={s.sheetHead}>
        <SideStamp side={side} />
        {q && (
          <p className={s.firstLine}>
            第一版{q.firstPassed ? "没有错误" : ` ${q.firstErrorCount} 条错误`}
            {q.repaired ? (q.finalPassed ? "，修正一次后通过" : `，修正一次后还有 ${q.finalErrorCount} 条`) : ""}
          </p>
        )}
      </div>
      {!version || !q ? (
        <p className={s.sideError}>{side.error ?? "没有行程"}</p>
      ) : (
        <>
          <PaperTitle level={3}>{version.title}</PaperTitle>
          {version.days.map((day) => (
            <section key={day.dayNumber} className={s.day}>
              <p className={s.dayHead}>
                第 {day.dayNumber} 天{day.date ? ` · ${day.date.slice(5).replace("-", ".")}` : ""}
                {day.theme ? ` · ${day.theme}` : ""}
              </p>
              <ol className={s.stops}>
                {day.stops.map((stop, i) => {
                  const leg = day.legs.find((l) => l.fromPoiId === day.stops[i - 1]?.poiId && l.toPoiId === stop.poiId);
                  const r = leg?.route;
                  return (
                    <li key={stop.poiId}>
                      {i > 0 && (
                        <p className={s.leg}>
                          ↓ {r && r.status === "ok" && r.durationMinutes != null ? `${MODE[r.mode]} ${r.durationMinutes} 分钟` : "交通没查到"}
                        </p>
                      )}
                      <p className={s.stop} data-only={only.has(stop.poiId)}>
                        <span className={s.time}>
                          {stop.arrive ? `${stop.arrive}–${stop.leave}` : "没排出时间"}
                        </span>{" "}
                        {stop.name}
                        {only.has(stop.poiId) && <span className={s.onlyTag}>只有这边</span>}
                      </p>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
          {version.validation.issues.some((i) => i.level === "error") ? (
            <>
              <Rule dashed />
              <p className={s.issuesHead}>还没解决的错误</p>
              <ul className={s.issues}>
                {version.validation.issues
                  .filter((i) => i.level === "error")
                  .map((i, n) => (
                    <li key={n}>✕ {i.message}</li>
                  ))}
              </ul>
            </>
          ) : null}
        </>
      )}
    </Paper>
  );
}

// ---------- 中间的评分卡 ----------

function ScoreCard({ cmp }: { cmp: ModelComparison }) {
  const notes = cmp.table.rows.filter((r) => r.note);
  return (
    <Paper kind="card" as="section" className={s.score} aria-label="评分卡">
      <PaperMark>评分卡 · 数字全部由程序算</PaperMark>
      <div className={s.tableWrap}>
        <table className={s.table}>
          <caption className="sr-only">两个模型的指标对比，数字由程序算</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">指标</span>
              </th>
              {cmp.table.labels.map((l) => (
                <th key={l} scope="col">
                  {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cmp.table.rows.map((row) => (
              <tr key={row.key}>
                <th scope="row">
                  {row.label}
                  {row.note && <sup aria-hidden="true">*</sup>}
                </th>
                {row.texts.map((t, i) => (
                  <td key={i}>{t}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className={s.notes}>
        {notes.map((r) => (
          <li key={r.key}>
            * {r.label}：{r.note}
          </li>
        ))}
        {cmp.extractorCalls && (
          <li>
            抽偏好由 {cmp.extractor} 做了一次，两边共用：{(cmp.extractorCalls.modelMs / 1000).toFixed(1)} 秒，不算在任何一边。
          </li>
        )}
      </ul>
      <p className={s.disclaimer}>
        <Soft>只列程序能算的数字，不让一个模型给另一个打分，也不下"哪个更好"的结论。一次对比只代表这一个请求、这一次运行。</Soft>
      </p>
    </Paper>
  );
}

// ---------- 差异 ----------

function names(refs: PoiRef[]): string {
  return refs.length ? refs.map((r) => r.name).join("、") : "没有";
}

function DiffCard({ diff, labels }: { diff: PlanDiff; labels: string[] }) {
  return (
    <Paper as="section" className={s.diff} aria-label="两份行程的差异">
      <PaperMark>差异 · 由程序比对</PaperMark>
      <PaperTitle level={3}>两份行程哪里不一样</PaperTitle>
      {diff.nearDuplicate && <p className={s.near}>两份几乎一样：{diff.nearDuplicate}。</p>}
      <dl className={s.diffList}>
        <dt>只有{labels[0]}选了</dt>
        <dd>{names(diff.onlyLeft)}</dd>
        <dt>只有{labels[1]}选了</dt>
        <dd>{names(diff.onlyRight)}</dd>
        <dt>两边都选了</dt>
        <dd>{names(diff.both)}</dd>
        {diff.moved.length > 0 && (
          <>
            <dt>排在不同的天</dt>
            <dd>
              {diff.moved.map((m) => `${m.name}（${labels[0]}第 ${m.days[0]} 天，${labels[1]}第 ${m.days[1]} 天）`).join("；")}
            </dd>
          </>
        )}
      </dl>
      <Rule dashed />
      <ul className={s.dayDiffs}>
        {diff.days.map((d) => (
          <li key={d.dayNumber}>
            <strong>第 {d.dayNumber} 天</strong>{" "}
            {d.sameOrder === null
              ? `两边都有的景点${d.common.length ? `只有 ${d.common[0].name}` : "没有"}，谈不上先后`
              : d.sameOrder
                ? `两边都有的 ${d.common.length} 个景点，先后顺序一样`
                : `两边都有的 ${d.common.length} 个景点，先后顺序不一样`}
            <span className={s.orders}>
              {labels.map((l, i) => (
                <span key={l}>
                  {l}：{d.orders[i]?.map((r) => r.name).join(" → ") || "没有景点"}
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </Paper>
  );
}

// ---------- 整页 ----------

export function CompareDesk() {
  const [text, setText] = useState("");
  const [emphasis, setEmphasis] = useState<Emphasis>("classic");
  const [job, setJob] = useState<CompareJob | null>(null);
  const [cmp, setCmp] = useState<ModelComparison | null>(null);
  const [history, setHistory] = useState<ModelComparisonSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshHistory = useCallback(() => {
    listComparisons()
      .then(setHistory)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "历史对比读不出来"));
  }, []);

  const open = useCallback((id: string) => {
    setError(null);
    getComparison(id)
      .then((c) => {
        setCmp(c);
        setTab(0);
        window.history.replaceState(null, "", `/compare?id=${encodeURIComponent(c.id)}`);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "这次对比读不出来"));
  }, []);

  useEffect(() => {
    refreshHistory();
    const id = new URLSearchParams(window.location.search).get("id");
    if (id) open(id);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [open, refreshHistory]);

  const poll = useCallback(
    (jobId: string) => {
      getCompareJob(jobId)
        .then((j) => {
          setJob(j);
          if (j.status === "completed" && j.comparisonId) {
            setJob(null);
            open(j.comparisonId);
            refreshHistory();
          } else if (j.status === "failed") {
            setJob(null);
            setError(j.error?.message ?? "对比没跑完");
          } else {
            timer.current = setTimeout(() => poll(jobId), 1000);
          }
        })
        .catch((e: unknown) => {
          setJob(null);
          setError(e instanceof ApiError ? e.message : "查不到进度");
        });
    },
    [open, refreshHistory],
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const request = text.trim();
    if (!request || job) return;
    setError(null);
    try {
      const started = await startComparison(request, emphasis);
      poll(started.jobId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "没发出去");
    }
  }

  const only = (i: number) => {
    if (!cmp?.diff) return new Set<string>();
    return new Set((i === 0 ? cmp.diff.onlyLeft : cmp.diff.onlyRight).map((r) => r.poiId));
  };

  return (
    <div className={s.layout}>
      <div className={s.work}>
        <Paper as="section" className={s.ask} aria-label="发起对比">
          <form onSubmit={submit}>
            <label className={s.askLabel} htmlFor="compare-request">
              一句话说清楚：玩几天、哪天出发、喜欢什么
            </label>
            <textarea
              id="compare-request"
              className={s.askInput}
              rows={2}
              maxLength={500}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="例如：武汉两天，喜欢历史和美食，坐地铁，11 月 28 日出发"
            />
            <div className={s.askRow} role="group" aria-label="侧重">
              <span className={s.askHint}>侧重</span>
              {EMPHASES.map((e) => (
                <NoteButton key={e.id} pressed={emphasis === e.id} onClick={() => setEmphasis(e.id)}>
                  {e.label}
                </NoteButton>
              ))}
              <BrassButton type="submit" disabled={!text.trim() || !!job} className={s.go}>
                {job ? "两边在排…" : "交给两个模型"}
              </BrassButton>
            </div>
            <p className={s.cost}>
              <Soft>
                一次对比调用模型 3 到 5 次：抽偏好 1 次（两边共用），千问和豆包各排行程 1 次，有错误的各修正 1 次。两边用同一份偏好、同一份候选、同一种侧重。
              </Soft>
            </p>
          </form>
          {error && <PencilNote className={s.error}>{error}</PencilNote>}
        </Paper>

        {job && (
          <Paper kind="card" as="section" className={s.progress} aria-live="polite" aria-label="对比进度">
            <PaperMark>进行中 · {job.request}</PaperMark>
            {job.stages.length > 0 && <p>{job.stages.map((st) => st.label).join(" → ")}</p>}
            <div className={s.progressSides}>
              {job.sides.map((side) => (
                <p key={side.provider}>
                  <strong>{side.label}</strong>：{side.stages.length ? side.stages.map((st) => st.label).join(" → ") : "等着"}
                </p>
              ))}
            </div>
          </Paper>
        )}

        {cmp && (
          <>
            <div className={s.summary}>
              <p className={s.summaryReq}>「{cmp.request}」</p>
              <p className={s.summaryMeta}>
                {cmp.emphasisLabel} · {prefsText(cmp.preferences)}
                {cmp.preferencesSource === "extracted" ? ` · 偏好由 ${cmp.extractor} 抽一次、两边共用` : " · 偏好是手写给定的"}
                {cmp.evalRequestId ? ` · 批量评测 ${cmp.evalRequestId}` : ""} · {when(cmp.createdAt)}
              </p>
            </div>
            <div className={s.tabs} role="group" aria-label="看哪一边">
              {cmp.sides.map((side, i) => (
                <NoteButton key={side.provider} pressed={tab === i} onClick={() => setTab(i)}>
                  {side.providerLabel}
                </NoteButton>
              ))}
            </div>
            <div className={s.desk}>
              {cmp.sides.map((side, i) => (
                <div key={side.provider} className={s.side} data-side={i} data-active={tab === i}>
                  <Sheet side={side} version={cmp.versions[i] ?? null} only={only(i)} />
                </div>
              ))}
              <ScoreCard cmp={cmp} />
            </div>
            {cmp.diff && <DiffCard diff={cmp.diff} labels={cmp.table.labels} />}
          </>
        )}

        {!cmp && !job && (
          <p className={s.empty}>
            还没有选中的对比。上面发起一次，或者从右边的历次对比里点开一张。
          </p>
        )}
      </div>

      <aside className={s.history} aria-label="历次对比">
        {/* 接口最多返回最近 50 条（GET /api/comparisons 的默认 limit），这里只写显示了几条，不当成总数 */}
        <p className={s.historyHead}>历次对比 · 最近 {history.length} 条</p>
        {history.length === 0 ? (
          <p className={s.historyEmpty}>还没有</p>
        ) : (
          <ul className={s.stack}>
            {history.map((h) => (
              <li key={h.id}>
                <button type="button" className={s.slip} aria-current={cmp?.id === h.id} onClick={() => open(h.id)}>
                  <span className={s.slipMeta}>
                    {when(h.createdAt)} · {h.emphasisLabel}
                    {h.evalRequestId ? ` · ${h.evalRequestId}` : ""}
                  </span>
                  <span className={s.slipReq}>{h.request}</span>
                  <span className={s.slipSides}>
                    {h.sides.map((b) => (
                      <span key={b.providerLabel}>
                        {b.providerLabel}：{b.error ? "没排出来" : `第一版${b.firstPassed ? "通过" : "未通过"}，最终${b.finalPassed ? "通过" : "未通过"}`}
                      </span>
                    ))}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
