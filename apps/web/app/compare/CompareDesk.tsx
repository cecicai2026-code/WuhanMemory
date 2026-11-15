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
import { useLang } from "@/components/i18n/LangProvider";
import { makeT, modelName, type Lang, type T } from "@/lib/i18n";
import s from "./compare.module.css";

type Both = { zh: string; en: string };
const EMPHASES: { id: Emphasis; label: Both }[] = [
  { id: "classic", label: { zh: "经典必去", en: "The classics" } },
  { id: "relaxed", label: { zh: "轻松少走路", en: "Easy, less walking" } },
  { id: "culture", label: { zh: "深度文化", en: "Deep culture" } },
];
const PACE = { relaxed: { zh: "轻松", en: "relaxed" }, moderate: { zh: "适中", en: "moderate" }, intensive: { zh: "紧凑", en: "packed" } } as const;
const PARTY = {
  solo: { zh: "一个人", en: "solo" },
  couple: { zh: "两个人", en: "a couple" },
  friends: { zh: "朋友", en: "friends" },
  family: { zh: "家庭", en: "family" },
  elderly: { zh: "带老人", en: "with older people" },
} as const;
const TRANSPORT = { metro: { zh: "地铁公交优先", en: "metro and bus first" }, walk: { zh: "尽量走路", en: "walk where possible" }, taxi: { zh: "打车", en: "taxi" } } as const;
const BUDGET = { low: { zh: "预算少", en: "low budget" }, medium: { zh: "预算中等", en: "medium budget" }, high: { zh: "预算多", en: "high budget" } } as const;
const MODE = { walk: { zh: "步行", en: "Walk" }, transit: { zh: "公交地铁", en: "Bus/metro" }, drive: { zh: "打车", en: "Taxi" } } as const;
const b = (x: Both, t: T) => t(x.zh, x.en);

function prefsText(p: TravelerPreferences, t: T): string {
  const sep = t("、", ", ");
  const parts: string[] = [];
  if (p.days) parts.push(t(`${p.days} 天`, `${p.days} days`));
  parts.push(p.startDate ? t(`${p.startDate} 出发`, `from ${p.startDate}`) : t("日期未定", "date not set"));
  if (p.pace) parts.push(t(`节奏${PACE[p.pace].zh}`, `${PACE[p.pace].en} pace`));
  if (p.party) parts.push(b(PARTY[p.party], t));
  if (p.transport) parts.push(b(TRANSPORT[p.transport], t));
  if (p.budget) parts.push(b(BUDGET[p.budget], t));
  if (p.interests.length) parts.push(t(`兴趣：${p.interests.join(sep)}`, `interests: ${p.interests.join(sep)}`));
  if (p.mustVisit.length) parts.push(t(`必去：${p.mustVisit.join(sep)}`, `must see: ${p.mustVisit.join(sep)}`));
  if (p.avoid.length) parts.push(t(`不去：${p.avoid.join(sep)}`, `skip: ${p.avoid.join(sep)}`));
  if (p.notes) parts.push(t(`其他：${p.notes}`, `other: ${p.notes}`));
  return parts.join(" · ");
}

function useTr(): { t: T; lang: Lang } {
  const lang = useLang();
  return { t: makeT(lang), lang };
}

function when(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}.${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ---------- 一边的打字纸 ----------

function SideStamp({ side }: { side: SideResult }) {
  const { t } = useTr();
  if (!side.quality) return <Stamp status="expired">{t("没排出来", "No plan")}</Stamp>;
  return side.quality.finalPassed ? (
    <Stamp status="verified">{t("通过校验", "Checks passed")}</Stamp>
  ) : (
    <Stamp status="expired">{t("未通过", "Failed")}</Stamp>
  );
}

function Sheet({ side, version, only }: { side: SideResult; version: ItineraryVersion | null; only: Set<string> }) {
  const { t, lang } = useTr();
  const q = side.quality;
  const who = modelName(side.providerLabel, lang);
  return (
    <Paper as="article" className={s.sheet} aria-label={t(`${who}排的行程`, `${who}'s trip`)}>
      <div className={s.bar}>
        <span className={s.barLabel}>{who}</span>
        <span className={s.barModel}>{side.model ?? t("模型名不详", "model name unknown")}</span>
      </div>
      <div className={s.sheetHead}>
        <SideStamp side={side} />
        {q && (
          <p className={s.firstLine}>
            {t(
              `第一版${q.firstPassed ? "没有错误" : ` ${q.firstErrorCount} 条错误`}${q.repaired ? (q.finalPassed ? "，修正一次后通过" : `，修正一次后还有 ${q.finalErrorCount} 条`) : ""}`,
              `First draft: ${q.firstPassed ? "no errors" : `${q.firstErrorCount} errors`}${q.repaired ? (q.finalPassed ? "; passed after one fix" : `; ${q.finalErrorCount} left after one fix`) : ""}`
            )}
          </p>
        )}
      </div>
      {!version || !q ? (
        <p className={s.sideError}>{side.error ?? t("没有行程", "No trip")}</p>
      ) : (
        <>
          <PaperTitle level={3}>{version.title}</PaperTitle>
          {version.days.map((day) => (
            <section key={day.dayNumber} className={s.day}>
              <p className={s.dayHead}>
                {t(`第 ${day.dayNumber} 天`, `Day ${day.dayNumber}`)}
                {day.date ? ` · ${day.date.slice(5).replace("-", ".")}` : ""}
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
                          ↓{" "}
                          {r && r.status === "ok" && r.durationMinutes != null
                            ? t(`${MODE[r.mode].zh} ${r.durationMinutes} 分钟`, `${MODE[r.mode].en} ${r.durationMinutes} min`)
                            : t("交通没查到", "No route found")}
                        </p>
                      )}
                      <p className={s.stop} data-only={only.has(stop.poiId)}>
                        <span className={s.time}>
                          {stop.arrive ? `${stop.arrive}–${stop.leave}` : t("没排出时间", "No time set")}
                        </span>{" "}
                        {stop.name}
                        {only.has(stop.poiId) && <span className={s.onlyTag}>{t("只有这边", "Only this side")}</span>}
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
              <p className={s.issuesHead}>{t("还没解决的错误", "Unresolved errors")}</p>
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
  const { t, lang } = useTr();
  const notes = cmp.table.rows.filter((r) => r.note);
  return (
    <Paper kind="card" as="section" className={s.score} aria-label={t("评分卡", "Scorecard")}>
      <PaperMark>{t("评分卡 · 数字全部由程序算", "Scorecard · every number computed by the program")}</PaperMark>
      <div className={s.tableWrap}>
        <table className={s.table}>
          <caption className="sr-only">{t("两个模型的指标对比，数字由程序算", "Metrics for the two models, computed by the program")}</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">{t("指标", "Metric")}</span>
              </th>
              {cmp.table.labels.map((l) => (
                <th key={l} scope="col">
                  {modelName(l, lang)}
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
                {row.texts.map((text, i) => (
                  <td key={i}>{text}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className={s.notes}>
        {notes.map((r) => (
          <li key={r.key}>
            * {r.label}
            {t("：", ": ")}
            {r.note}
          </li>
        ))}
        {cmp.extractorCalls && (
          <li>
            {t(
              `抽偏好由 ${cmp.extractor} 做了一次，两边共用：${(cmp.extractorCalls.modelMs / 1000).toFixed(1)} 秒，不算在任何一边。`,
              `Preferences were extracted once by ${cmp.extractor ? modelName(cmp.extractor, lang) : ""} and shared by both sides: ${(cmp.extractorCalls.modelMs / 1000).toFixed(1)} s, not counted on either side.`
            )}
          </li>
        )}
      </ul>
      <p className={s.disclaimer}>
        <Soft>
          {t(
            '只列程序能算的数字，不让一个模型给另一个打分，也不下"哪个更好"的结论。一次对比只代表这一个请求、这一次运行。',
            "Only numbers the program can compute are listed. Neither model grades the other, and there is no verdict on which is better. One comparison covers only this request and this run."
          )}
        </Soft>
      </p>
    </Paper>
  );
}

// ---------- 差异 ----------

function names(refs: PoiRef[], t: T): string {
  return refs.length ? refs.map((r) => r.name).join(t("、", ", ")) : t("没有", "none");
}

function DiffCard({ diff, labels: raw }: { diff: PlanDiff; labels: string[] }) {
  const { t, lang } = useTr();
  const labels = raw.map((l) => modelName(l, lang));
  return (
    <Paper as="section" className={s.diff} aria-label={t("两份行程的差异", "Differences between the two trips")}>
      <PaperMark>{t("差异 · 由程序比对", "Differences · compared by the program")}</PaperMark>
      <PaperTitle level={3}>{t("两份行程哪里不一样", "Where the two trips differ")}</PaperTitle>
      {diff.nearDuplicate && <p className={s.near}>{t(`两份几乎一样：${diff.nearDuplicate}。`, `The two are almost the same: ${diff.nearDuplicate}.`)}</p>}
      <dl className={s.diffList}>
        <dt>{t(`只有${labels[0]}选了`, `Only ${labels[0]} picked`)}</dt>
        <dd>{names(diff.onlyLeft, t)}</dd>
        <dt>{t(`只有${labels[1]}选了`, `Only ${labels[1]} picked`)}</dt>
        <dd>{names(diff.onlyRight, t)}</dd>
        <dt>{t("两边都选了", "Both picked")}</dt>
        <dd>{names(diff.both, t)}</dd>
        {diff.moved.length > 0 && (
          <>
            <dt>{t("排在不同的天", "On different days")}</dt>
            <dd>
              {diff.moved
                .map((m) =>
                  t(
                    `${m.name}（${labels[0]}第 ${m.days[0]} 天，${labels[1]}第 ${m.days[1]} 天）`,
                    `${m.name} (${labels[0]}: day ${m.days[0]}, ${labels[1]}: day ${m.days[1]})`
                  )
                )
                .join(t("；", "; "))}
            </dd>
          </>
        )}
      </dl>
      <Rule dashed />
      <ul className={s.dayDiffs}>
        {diff.days.map((d) => (
          <li key={d.dayNumber}>
            <strong>{t(`第 ${d.dayNumber} 天`, `Day ${d.dayNumber}`)}</strong>{" "}
            {d.sameOrder === null
              ? t(
                  `两边都有的景点${d.common.length ? `只有 ${d.common[0].name}` : "没有"}，谈不上先后`,
                  `${d.common.length ? `Only ${d.common[0].name} is` : "No place is"} on both sides, so there is no order to compare`
                )
              : d.sameOrder
                ? t(`两边都有的 ${d.common.length} 个景点，先后顺序一样`, `The ${d.common.length} places on both sides are in the same order`)
                : t(`两边都有的 ${d.common.length} 个景点，先后顺序不一样`, `The ${d.common.length} places on both sides are in a different order`)}
            <span className={s.orders}>
              {labels.map((l, i) => (
                <span key={l}>
                  {l}
                  {t("：", ": ")}
                  {d.orders[i]?.map((r) => r.name).join(" → ") || t("没有景点", "no places")}
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
  const { t, lang } = useTr();
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
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("历史对比读不出来", "Couldn't read past comparisons")));
  }, [t]);

  const open = useCallback((id: string) => {
    setError(null);
    getComparison(id)
      .then((c) => {
        setCmp(c);
        setTab(0);
        window.history.replaceState(null, "", `/compare?id=${encodeURIComponent(c.id)}`);
      })
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : t("这次对比读不出来", "Couldn't read this comparison")));
  }, [t]);

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
            setError(j.error?.message ?? t("对比没跑完", "The comparison didn't finish"));
          } else {
            timer.current = setTimeout(() => poll(jobId), 1000);
          }
        })
        .catch((e: unknown) => {
          setJob(null);
          setError(e instanceof ApiError ? e.message : t("查不到进度", "Couldn't get progress"));
        });
    },
    [open, refreshHistory, t],
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
      setError(err instanceof ApiError ? err.message : t("没发出去", "Not sent"));
    }
  }

  const only = (i: number) => {
    if (!cmp?.diff) return new Set<string>();
    return new Set((i === 0 ? cmp.diff.onlyLeft : cmp.diff.onlyRight).map((r) => r.poiId));
  };

  return (
    <div className={s.layout}>
      <div className={s.work}>
        <Paper as="section" className={s.ask} aria-label={t("发起对比", "Start a comparison")}>
          <form onSubmit={submit}>
            <label className={s.askLabel} htmlFor="compare-request">
              {t("一句话说清楚：玩几天、哪天出发、喜欢什么", "In one sentence: how many days, when you start, what you like")}
            </label>
            <textarea
              id="compare-request"
              className={s.askInput}
              rows={2}
              maxLength={500}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("例如：武汉两天，喜欢历史和美食，坐地铁，11 月 28 日出发", "e.g. Two days in Wuhan, history and food, by metro, starting 28 November")}
            />
            <div className={s.askRow} role="group" aria-label={t("侧重", "Emphasis")}>
              <span className={s.askHint}>{t("侧重", "Emphasis")}</span>
              {EMPHASES.map((e) => (
                <NoteButton key={e.id} pressed={emphasis === e.id} onClick={() => setEmphasis(e.id)}>
                  {b(e.label, t)}
                </NoteButton>
              ))}
              <BrassButton type="submit" disabled={!text.trim() || !!job} className={s.go}>
                {job ? t("两边在排…", "Both are planning…") : t("交给两个模型", "Send to both models")}
              </BrassButton>
            </div>
            <p className={s.cost}>
              <Soft>
                {t(
                  "一次对比调用模型 3 到 5 次：抽偏好 1 次（两边共用），千问和豆包各排行程 1 次，有错误的各修正 1 次。两边用同一份偏好、同一份候选、同一种侧重。",
                  "One comparison calls the models 3 to 5 times: preferences are extracted once (shared by both sides), Qwen and Doubao each plan once, and each side with errors gets one fix. Both sides use the same preferences, candidates and emphasis."
                )}
              </Soft>
            </p>
          </form>
          {error && <PencilNote className={s.error}>{error}</PencilNote>}
        </Paper>

        {job && (
          <Paper kind="card" as="section" className={s.progress} aria-live="polite" aria-label={t("对比进度", "Comparison progress")}>
            <PaperMark>
              {t("进行中 · ", "In progress · ")}
              {job.request}
            </PaperMark>
            {job.stages.length > 0 && <p>{job.stages.map((st) => st.label).join(" → ")}</p>}
            <div className={s.progressSides}>
              {job.sides.map((side) => (
                <p key={side.provider}>
                  <strong>{modelName(side.label, lang)}</strong>
                  {t("：", ": ")}
                  {side.stages.length ? side.stages.map((st) => st.label).join(" → ") : t("等着", "waiting")}
                </p>
              ))}
            </div>
          </Paper>
        )}

        {cmp && (
          <>
            <div className={s.summary}>
              <p className={s.summaryReq}>{t(`「${cmp.request}」`, `“${cmp.request}”`)}</p>
              <p className={s.summaryMeta}>
                {cmp.emphasisLabel} · {prefsText(cmp.preferences, t)}
                {cmp.preferencesSource === "extracted"
                  ? t(` · 偏好由 ${cmp.extractor} 抽一次、两边共用`, ` · preferences extracted once by ${cmp.extractor ? modelName(cmp.extractor, lang) : ""}, shared by both`)
                  : t(" · 偏好是手写给定的", " · preferences written by hand")}
                {cmp.evalRequestId ? t(` · 批量评测 ${cmp.evalRequestId}`, ` · batch eval ${cmp.evalRequestId}`) : ""} · {when(cmp.createdAt)}
              </p>
            </div>
            <div className={s.tabs} role="group" aria-label={t("看哪一边", "Which side to view")}>
              {cmp.sides.map((side, i) => (
                <NoteButton key={side.provider} pressed={tab === i} onClick={() => setTab(i)}>
                  {modelName(side.providerLabel, lang)}
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
            {t(
              "还没有选中的对比。上面发起一次，或者从右边的历次对比里点开一张。",
              "No comparison selected. Start one above, or open one from past comparisons on the right."
            )}
          </p>
        )}
      </div>

      <aside className={s.history} aria-label={t("历次对比", "Past comparisons")}>
        {/* 接口最多返回最近 50 条（GET /api/comparisons 的默认 limit），这里只写显示了几条，不当成总数 */}
        <p className={s.historyHead}>{t(`历次对比 · 最近 ${history.length} 条`, `Past comparisons · latest ${history.length}`)}</p>
        {history.length === 0 ? (
          <p className={s.historyEmpty}>{t("还没有", "None yet")}</p>
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
                    {h.sides.map((sd) => (
                      <span key={sd.providerLabel}>
                        {modelName(sd.providerLabel, lang)}
                        {t("：", ": ")}
                        {sd.error
                          ? t("没排出来", "no plan")
                          : t(
                              `第一版${sd.firstPassed ? "通过" : "未通过"}，最终${sd.finalPassed ? "通过" : "未通过"}`,
                              `first draft ${sd.firstPassed ? "passed" : "failed"}, final ${sd.finalPassed ? "passed" : "failed"}`
                            )}
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
