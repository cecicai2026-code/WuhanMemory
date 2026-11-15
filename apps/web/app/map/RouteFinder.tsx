"use client";

import { useState } from "react";
import type { PoiSummary, Route, RouteCompare, RouteMode } from "@wuhanmemory/shared";
import { BrassButton, Paper, PaperMark, PaperTitle, PencilNote, Stamp } from "@/components/ui";
import { backendDownMessage, backendStatusMessage } from "@/lib/backend";
import { useLang } from "@/components/i18n/LangProvider";
import { makeT, type Lang, type T } from "@/lib/i18n";
import s from "./map.module.css";


export const MODE_TEXT: Record<RouteMode, { zh: string; en: string }> = {
  walk: { zh: "步行", en: "Walk" },
  transit: { zh: "公交地铁", en: "Bus and metro" },
  drive: { zh: "驾车 / 打车", en: "Car / taxi" },
};

const locale = (lang: Lang) => (lang === "en" ? "en-GB" : "zh-CN");
const timeFmt = (lang: Lang) =>
  new Intl.DateTimeFormat(locale(lang), { timeZone: "Asia/Shanghai", month: lang === "en" ? "short" : "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
const dateFmt = (lang: Lang) => new Intl.DateTimeFormat(locale(lang), { timeZone: "Asia/Shanghai", month: lang === "en" ? "short" : "numeric", day: "numeric" });

function distance(m: number | null, t: T): string | null {
  if (m == null) return null;
  return m < 1000 ? t(`${m} 米`, `${m} m`) : t(`${(m / 1000).toFixed(1)} 公里`, `${(m / 1000).toFixed(1)} km`);
}

function cost(r: Route, t: T): string | null {
  if (!r.cost) return null;
  if (r.cost.kind === "free") return t("不花钱", "Free");
  if (r.cost.amountCny == null) return r.cost.note;
  return r.cost.kind === "taxi" ? t(`打车约 ${r.cost.amountCny} 元`, `Taxi about ¥${r.cost.amountCny}`) : t(`票价约 ${r.cost.amountCny} 元`, `Fare about ¥${r.cost.amountCny}`);
}

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; data: RouteCompare }
  | { kind: "error"; message: string };

interface Props {
  pois: PoiSummary[];
  /** 当前画在地图上的是哪一种 */
  shown: RouteMode | null;
  onShow: (route: Route | null) => void;
}

/**
 * 临时的"两点之间怎么走"（板块 3）：选两个景点，看步行、公交地铁、驾车的对比，
 * 点一种就把它的路线画在地图上。板块 5 的行程用同一个接口 /api/routes/compare。
 */
export function RouteFinder({ pois, shown, onShow }: Props) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const lang = useLang();
  const t = makeT(lang);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!from || !to || from === to) return;
    setState({ kind: "loading" });
    onShow(null);
    let res: Response;
    try {
      res = await fetch(`/api/routes/compare?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&lang=${lang}`);
    } catch {
      setState({ kind: "error", message: backendDownMessage(lang) });
      return;
    }
    if (!res.ok) {
      const detail = await res.json().then((b: { detail?: string }) => b.detail).catch(() => null);
      setState({ kind: "error", message: detail ?? (res.status >= 500 ? backendDownMessage(lang) : backendStatusMessage(res.status, lang)) });
      return;
    }
    const data = (await res.json()) as RouteCompare;
    setState({ kind: "done", data });
    // 先在地图上画第一种有方案的
    onShow(data.routes.find((r) => r.status === "ok" && r.polyline.length > 1) ?? null);
  }

  const same = from !== "" && from === to;

  return (
    <Paper kind="card" className={s.finder} aria-label={t("两点之间怎么走", "Getting between two places")}>
      <PaperMark>{t("索引卡 · 临时", "Index card · temporary")}</PaperMark>
      <PaperTitle level={3}>{t("两点之间怎么走", "Getting between two places")}</PaperTitle>
      <form className={s.finderForm} onSubmit={search}>
        <label className={s.pick}>
          <span>{t("从", "From")}</span>
          <select aria-label={t("起点", "Start")} value={from} onChange={(e) => setFrom(e.target.value)} required>
            <option value="">{t("选起点", "Pick a start")}</option>
            {pois.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className={s.pick}>
          <span>{t("到", "To")}</span>
          <select aria-label={t("终点", "End")} value={to} onChange={(e) => setTo(e.target.value)} required>
            <option value="">{t("选终点", "Pick an end")}</option>
            {pois.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {same && <PencilNote>{t("起点和终点是同一个地方", "Start and end are the same place")}</PencilNote>}
        <BrassButton type="submit" disabled={!from || !to || same || state.kind === "loading"}>
          {state.kind === "loading" ? t("查询中……", "Looking up…") : t("查路线", "Find routes")}
        </BrassButton>
      </form>

      {state.kind === "error" && (
        <p className={s.routeError} role="alert">
          {t("没查成：", "Lookup failed: ")}
          {state.message}
        </p>
      )}

      {state.kind === "done" && (
        <ul className={s.routes} aria-live="polite">
          {state.data.routes.map((r) => {
            const drawable = r.status === "ok" && r.polyline.length > 1;
            const facts = [r.durationMinutes != null ? t(`约 ${r.durationMinutes} 分钟`, `about ${r.durationMinutes} min`) : null, distance(r.distanceMeters, t), cost(r, t)].filter(Boolean);
            return (
              <li key={r.mode} className={s.route} data-shown={shown === r.mode || undefined}>
                <div className={s.routeHead}>
                  <strong>{t(MODE_TEXT[r.mode].zh, MODE_TEXT[r.mode].en)}</strong>
                  {r.cache === "stale" && <Stamp status="expired" />}
                  {drawable && (
                    <button type="button" className={s.showLine} aria-pressed={shown === r.mode} onClick={() => onShow(r)}>
                      {shown === r.mode ? t("地图上显示中", "Showing on the map") : t("在地图上看", "Show on the map")}
                    </button>
                  )}
                </div>
                {r.status === "ok" && <p>{facts.join(" · ")}</p>}
                {r.summary && <p>{r.summary}</p>}
                {r.status === "none" && <p>{r.reason}</p>}
                {r.status === "error" && (
                  <p className={s.routeError}>
                    {t("没查成：", "Lookup failed: ")}
                    {r.error?.message}
                  </p>
                )}
                {r.warning && <p className={s.routeError}>{r.warning}</p>}
                {r.checkedAt && r.expiresAt && (
                  <p className={s.routeMeta}>
                    {t(
                      `高德 · ${timeFmt(lang).format(new Date(r.checkedAt))} 查询 · ${dateFmt(lang).format(new Date(r.expiresAt))} 过期`,
                      `AMap · looked up ${timeFmt(lang).format(new Date(r.checkedAt))} · expires ${dateFmt(lang).format(new Date(r.expiresAt))}`
                    )}
                    {r.cost && r.cost.kind !== "free" && r.cost.amountCny != null ? ` · ${r.cost.note}` : ""}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Paper>
  );
}
