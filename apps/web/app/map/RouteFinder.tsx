"use client";

import { useState } from "react";
import type { PoiSummary, Route, RouteCompare, RouteMode } from "@wuhanmemory/shared";
import { BrassButton, Paper, PaperMark, PaperTitle, PencilNote, Stamp } from "@/components/ui";
import s from "./map.module.css";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

const MODE_TEXT: Record<RouteMode, string> = { walk: "步行", transit: "公交地铁", drive: "驾车 / 打车" };

const TIME_FMT = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const DATE_FMT = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", month: "numeric", day: "numeric" });

function distance(m: number | null): string | null {
  if (m == null) return null;
  return m < 1000 ? `${m} 米` : `${(m / 1000).toFixed(1)} 公里`;
}

function cost(r: Route): string | null {
  if (!r.cost) return null;
  if (r.cost.kind === "free") return "不花钱";
  if (r.cost.amountCny == null) return r.cost.note;
  return `${r.cost.kind === "taxi" ? "打车约" : "票价约"} ${r.cost.amountCny} 元`;
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

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!from || !to || from === to) return;
    setState({ kind: "loading" });
    onShow(null);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/routes/compare?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
    } catch {
      setState({ kind: "error", message: `连不上后端 ${API_BASE}。先启动后端：corepack pnpm dev:api` });
      return;
    }
    if (!res.ok) {
      const detail = await res.json().then((b: { detail?: string }) => b.detail).catch(() => null);
      setState({ kind: "error", message: detail ?? `后端返回 ${res.status}` });
      return;
    }
    const data = (await res.json()) as RouteCompare;
    setState({ kind: "done", data });
    // 先在地图上画第一种有方案的
    onShow(data.routes.find((r) => r.status === "ok" && r.polyline.length > 1) ?? null);
  }

  const same = from !== "" && from === to;

  return (
    <Paper kind="card" className={s.finder} aria-label="两点之间怎么走">
      <PaperMark>索引卡 · 临时</PaperMark>
      <PaperTitle level={3}>两点之间怎么走</PaperTitle>
      <form className={s.finderForm} onSubmit={search}>
        <label className={s.pick}>
          <span>从</span>
          <select value={from} onChange={(e) => setFrom(e.target.value)} required>
            <option value="">选起点</option>
            {pois.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className={s.pick}>
          <span>到</span>
          <select value={to} onChange={(e) => setTo(e.target.value)} required>
            <option value="">选终点</option>
            {pois.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {same && <PencilNote>起点和终点是同一个地方</PencilNote>}
        <BrassButton type="submit" disabled={!from || !to || same || state.kind === "loading"}>
          {state.kind === "loading" ? "查询中……" : "查路线"}
        </BrassButton>
      </form>

      {state.kind === "error" && (
        <p className={s.routeError} role="alert">
          没查成：{state.message}
        </p>
      )}

      {state.kind === "done" && (
        <ul className={s.routes} aria-live="polite">
          {state.data.routes.map((r) => {
            const drawable = r.status === "ok" && r.polyline.length > 1;
            const facts = [r.durationMinutes != null ? `约 ${r.durationMinutes} 分钟` : null, distance(r.distanceMeters), cost(r)].filter(Boolean);
            return (
              <li key={r.mode} className={s.route} data-shown={shown === r.mode || undefined}>
                <div className={s.routeHead}>
                  <strong>{MODE_TEXT[r.mode]}</strong>
                  {r.cache === "stale" && <Stamp status="expired" />}
                  {drawable && (
                    <button type="button" className={s.showLine} aria-pressed={shown === r.mode} onClick={() => onShow(r)}>
                      {shown === r.mode ? "地图上显示中" : "在地图上看"}
                    </button>
                  )}
                </div>
                {r.status === "ok" && <p>{facts.join(" · ")}</p>}
                {r.summary && <p>{r.summary}</p>}
                {r.status === "none" && <p>{r.reason}</p>}
                {r.status === "error" && <p className={s.routeError}>没查成：{r.error?.message}</p>}
                {r.warning && <p className={s.routeError}>{r.warning}</p>}
                {r.checkedAt && r.expiresAt && (
                  <p className={s.routeMeta}>
                    高德 · {TIME_FMT.format(new Date(r.checkedAt))} 查询 · {DATE_FMT.format(new Date(r.expiresAt))} 过期
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
