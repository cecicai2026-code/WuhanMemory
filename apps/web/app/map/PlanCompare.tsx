"use client";

import type { PlanningRound } from "@wuhanmemory/shared";
import { NoteButton, Paper, PaperMark, PaperTitle, Rule, Soft } from "@/components/ui";
import s from "./map.module.css";

interface Props {
  round: PlanningRound;
  /** 选中的是 round.versions 里的第几份 */
  picked: number;
  onPick: (index: number) => void;
}

/**
 * 一轮方案的总卡（板块 5B）：切换看哪一份、几份之间的对比表、没展示的是哪几份和为什么。
 * 表里每一格都是后端程序算好的文字（metrics.py），这里不算数，也不写"哪份更好"。
 */
export function PlanCompare({ round, picked, onPick }: Props) {
  const shown = round.plans.filter((p) => p.shown);
  const hidden = round.plans.filter((p) => !p.shown);
  const cmp = round.comparison;
  const notes = cmp ? cmp.rows.filter((r) => r.note) : [];

  return (
    <Paper kind="card" tilt={1} as="section" aria-label="方案对比">
      <PaperMark>
        第 {round.roundNumber} 轮 · {round.providerLabel} · 排了 {round.plans.length} 份，展示 {shown.length} 份
      </PaperMark>
      <PaperTitle level={3}>{shown.length > 1 ? "几份方案对比" : shown.length === 1 ? "这一轮的方案" : "这一轮没有能展示的方案"}</PaperTitle>

      {shown.length > 1 && (
        <div className={s.planPick} role="group" aria-label="看哪一份方案">
          {shown.map((p, i) => (
            <NoteButton key={p.emphasis} pressed={picked === i} onClick={() => onPick(i)}>
              {p.label}
            </NoteButton>
          ))}
        </div>
      )}

      {cmp && cmp.labels.length > 1 && (
        <div className={s.compareWrap}>
          <table className={s.compare}>
            <caption className="sr-only">几份方案的对比，数字由程序算</caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="sr-only">项目</span>
                </th>
                {cmp.labels.map((label, i) => (
                  <th key={label} scope="col" data-picked={picked === i}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cmp.rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}
                    {row.note && <sup aria-hidden="true">*</sup>}
                  </th>
                  {row.texts.map((t, i) => (
                    <td key={i} data-picked={picked === i}>
                      {t}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {notes.length > 0 && cmp && cmp.labels.length > 1 && (
        <ul className={s.compareNotes}>
          {notes.map((r) => (
            <li key={r.key}>
              * {r.label}：{r.note}
            </li>
          ))}
        </ul>
      )}

      {hidden.length > 0 && (
        <>
          <Rule dashed />
          <p className={s.issuesHead}>没展示的 {hidden.length} 份</p>
          <ul className={s.hiddenPlans}>
            {hidden.map((p) => (
              <li key={p.emphasis}>
                <strong>「{p.label}」</strong> {p.removedReason}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className={s.legend}>
        <Soft>三种侧重由程序定规则，模型分别排；表里的数字由程序从高德和景点库算出来。</Soft>
      </p>
    </Paper>
  );
}
