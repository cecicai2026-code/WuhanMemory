"use client";

import { useEffect, useState } from "react";
import type { LlmError, LlmPing, LlmProviderId, LlmProviders } from "@wuhanmemory/shared";
import s from "./map.module.css";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
/** 上次选的模型记在浏览器里，下次打开还是它。只是个方便，后端不依赖它 */
const STORAGE_KEY = "wuhanmemory.llm-provider";

type Load = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; data: LlmProviders };

type Ping =
  | { kind: "idle" }
  | { kind: "asking"; label: string }
  | { kind: "done"; data: LlmPing }
  | { kind: "error"; message: string };

function remembered(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function remember(id: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // 无痕窗口等情况下存不了，不影响使用
  }
}

function seconds(ms: number): string {
  return ms < 1000 ? `${ms} 毫秒` : `${(ms / 1000).toFixed(1)} 秒`;
}

async function errorMessage(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as { detail?: LlmError | string } | null;
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  return `后端返回 ${res.status}`;
}

interface Props {
  /** 现在选的模型。null：还没选出来（正在取清单，或者一个都没配置） */
  value: LlmProviderId | null;
  onChange: (id: LlmProviderId | null) => void;
}

/**
 * 模型选择（板块 4）：千问和豆包选一个，没配置 key 的选不了。
 * 有哪些模型、配没配置，从后端 GET /api/llm/providers 取；key 只在后端。
 *
 * "试一句"是临时的：给选中的模型发一句固定的话，看切换确实生效。
 * 每点一次是一次真实调用。板块 5 接上对话后去掉。
 */
export function ModelPicker({ value, onChange }: Props) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [ping, setPing] = useState<Ping>({ kind: "idle" });

  useEffect(() => {
    let closed = false;
    (async () => {
      let res: Response;
      try {
        res = await fetch(`${API_BASE}/api/llm/providers`, { cache: "no-store" });
      } catch {
        if (!closed) setLoad({ kind: "error", message: `连不上后端 ${API_BASE}。先启动后端：corepack pnpm dev:api` });
        return;
      }
      if (closed) return;
      if (!res.ok) {
        setLoad({ kind: "error", message: await errorMessage(res) });
        return;
      }
      const data = (await res.json()) as LlmProviders;
      if (closed) return;
      setLoad({ kind: "ready", data });
      // 先用上次选的；没有就用 .env 里的默认模型；再没有就用第一个配置好的
      const usable = data.providers.filter((p) => p.configured);
      const last = remembered();
      const first =
        usable.find((p) => p.id === last) ?? usable.find((p) => p.id === data.defaultProvider) ?? usable[0] ?? null;
      onChange(first ? first.id : null);
    })();
    return () => {
      closed = true;
    };
    // 只在打开页面时取一次
  }, []);

  function choose(id: LlmProviderId) {
    onChange(id);
    remember(id);
  }

  async function tryOnce() {
    if (load.kind !== "ready" || !value) return;
    const label = load.data.providers.find((p) => p.id === value)?.label ?? value;
    setPing({ kind: "asking", label });
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/llm/ping`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ provider: value }),
      });
    } catch {
      setPing({ kind: "error", message: `连不上后端 ${API_BASE}` });
      return;
    }
    if (!res.ok) {
      setPing({ kind: "error", message: await errorMessage(res) });
      return;
    }
    setPing({ kind: "done", data: (await res.json()) as LlmPing });
  }

  if (load.kind === "loading") {
    return (
      <div className={s.models}>
        <span className={s.modelsLegend}>模型</span>
        <p className={s.modelsNote}>正在取模型清单……</p>
      </div>
    );
  }
  if (load.kind === "error") {
    return (
      <div className={s.models}>
        <span className={s.modelsLegend}>模型</span>
        <p className={s.routeError} role="alert">
          没取到模型清单：{load.message}
        </p>
      </div>
    );
  }

  const { providers } = load.data;
  const noneConfigured = providers.every((p) => !p.configured);

  return (
    <fieldset className={s.models}>
      <legend className={s.modelsLegend}>模型</legend>
      <div className={s.modelRow}>
        {providers.map((p) => (
          <label
            key={p.id}
            className={s.model}
            data-checked={value === p.id || undefined}
            data-disabled={!p.configured || undefined}
          >
            <input
              type="radio"
              name="llm-provider"
              value={p.id}
              checked={value === p.id}
              disabled={!p.configured}
              onChange={() => choose(p.id)}
            />
            <span aria-hidden="true" className={s.modelTick}>
              {value === p.id ? "✓" : ""}
            </span>
            {p.label}
            {!p.configured && "（没配置）"}
          </label>
        ))}
        <button
          type="button"
          className={s.tryOne}
          disabled={!value || ping.kind === "asking"}
          onClick={tryOnce}
        >
          {ping.kind === "asking" ? "等回答……" : "试一句"}
        </button>
      </div>

      {noneConfigured && <p className={s.modelsNote}>两个模型都还没配置：在 apps/api/.env 里填 key，再重启后端。</p>}

      <div className={s.pingResult} aria-live="polite">
        {ping.kind === "asking" && <p className={s.modelsNote}>已经发给{ping.label}，等它回答……</p>}
        {ping.kind === "error" && (
          <p className={s.routeError} role="alert">
            没问成：{ping.message}
          </p>
        )}
        {ping.kind === "done" && (
          <>
            <p className={s.pingReply}>“{ping.data.reply}”</p>
            <p className={s.routeMeta}>
              {ping.data.label} · {ping.data.model} · {seconds(ping.data.latencyMs)}
              {ping.data.retried ? " · 重试过" : ""}
              {ping.data.repaired ? " · 让模型重答过" : ""}
            </p>
          </>
        )}
        {ping.kind === "idle" && !noneConfigured && <p className={`${s.modelsNote} ${s.tryNote}`}>试一句是临时的，板块 5 接上对话后去掉</p>}
      </div>
    </fieldset>
  );
}
