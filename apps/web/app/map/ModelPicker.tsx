"use client";

import { useEffect, useState } from "react";
import type { LlmProviderId, LlmProviders } from "@wuhanmemory/shared";
import { backendDownMessage } from "@/lib/backend";
import { API_BASE, ApiError } from "@/lib/planning-client";
import s from "./map.module.css";

/** 上次选的模型记在浏览器里，下次打开还是它。只是个方便，后端不依赖它 */
const STORAGE_KEY = "wuhanmemory.llm-provider";

type Load = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; data: LlmProviders };

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

async function loadProviders(): Promise<LlmProviders> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/llm/providers`, { cache: "no-store" });
  } catch {
    throw new ApiError(backendDownMessage(), null);
  }
  if (!res.ok) throw new ApiError(`后端返回 ${res.status}`, res.status);
  return (await res.json()) as LlmProviders;
}

interface Props {
  /** 现在选的模型。null：还没选出来（正在取清单，或者一个都没配置） */
  value: LlmProviderId | null;
  onChange: (id: LlmProviderId | null, label: string | null) => void;
  /** 规划进行中时不让换模型 */
  disabled?: boolean;
  /** 取到清单后告诉外面每个模型的中文名，对话纸上标注每条回复用的模型 */
  onLoaded?: (labels: Record<string, string>) => void;
}

/**
 * 模型选择（板块 4）：千问和豆包选一个，没配置 key 的选不了。
 * 有哪些模型、配没配置，从后端 GET /api/llm/providers 取；key 只在后端。
 * 选中的模型跟着每条消息发给后端（板块 5）。
 */
export function ModelPicker({ value, onChange, disabled, onLoaded }: Props) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    let closed = false;
    loadProviders()
      .then((data) => {
        if (closed) return;
        setLoad({ kind: "ready", data });
        onLoaded?.(Object.fromEntries(data.providers.map((p) => [p.id, p.label])));
        // 先用上次选的；没有就用 .env 里的默认模型；再没有就用第一个配置好的
        const usable = data.providers.filter((p) => p.configured);
        const last = remembered();
        const first =
          usable.find((p) => p.id === last) ?? usable.find((p) => p.id === data.defaultProvider) ?? usable[0] ?? null;
        onChange(first ? first.id : null, first ? first.label : null);
      })
      .catch((err: unknown) => {
        if (!closed) setLoad({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => {
      closed = true;
    };
    // 只在打开页面时取一次
  }, []);

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
    <fieldset className={s.models} disabled={disabled}>
      <legend className={s.modelsLegend}>模型</legend>
      <div className={s.modelRow}>
        {providers.map((p) => (
          <label
            key={p.id}
            className={s.model}
            data-checked={value === p.id || undefined}
            data-disabled={!p.configured || disabled || undefined}
          >
            <input
              type="radio"
              name="llm-provider"
              value={p.id}
              checked={value === p.id}
              disabled={!p.configured || disabled}
              onChange={() => {
                onChange(p.id, p.label);
                remember(p.id);
              }}
            />
            <span aria-hidden="true" className={s.modelTick}>
              {value === p.id ? "✓" : ""}
            </span>
            {p.label}
            {!p.configured && "（没配置）"}
          </label>
        ))}
      </div>
      {noneConfigured && <p className={s.modelsNote}>两个模型都还没配置：在 apps/api/.env 里填 key，再重启后端。</p>}
    </fieldset>
  );
}
