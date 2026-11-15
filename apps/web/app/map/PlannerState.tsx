"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { LlmProviderId, ValidationStatus } from "@wuhanmemory/shared";
import { Label } from "@/components/ui";

/**
 * 地图工作台里几处共用的状态：选中的模型（板块 4 的模型选择）和当前行程的校验结果。
 * 四角标注（右上角）在 Scene 的页眉里，不在 Workbench 里面，所以用一个 context 把它们连起来。
 * 设计规范第 7 节：四角标注只显示真实的值，其中包括当前模型和校验结果。
 */
interface PlannerState {
  provider: LlmProviderId | null;
  providerLabel: string | null;
  setProvider: (id: LlmProviderId | null, label: string | null) => void;
  validation: ValidationStatus | null;
  /** 当前显示的行程是哪个模型排的 */
  validationBy: string | null;
  setValidation: (status: ValidationStatus | null, by?: string | null) => void;
}

const Ctx = createContext<PlannerState | null>(null);

export function PlannerStateProvider({ children }: { children: ReactNode }) {
  const [provider, setProviderId] = useState<LlmProviderId | null>(null);
  const [providerLabel, setProviderLabel] = useState<string | null>(null);
  const [validation, setValidationStatus] = useState<ValidationStatus | null>(null);
  const [validationBy, setValidationBy] = useState<string | null>(null);
  // 两个 setter 保持同一个函数，用到它们的 effect 不会因为状态变了而重跑
  const setProvider = useCallback((id: LlmProviderId | null, label: string | null) => {
    setProviderId(id);
    setProviderLabel(label);
  }, []);
  const setValidation = useCallback((status: ValidationStatus | null, by: string | null = null) => {
    setValidationStatus(status);
    setValidationBy(status ? by : null);
  }, []);
  const value = useMemo<PlannerState>(
    () => ({ provider, providerLabel, setProvider, validation, validationBy, setValidation }),
    [provider, providerLabel, setProvider, validation, validationBy, setValidation],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePlannerState(): PlannerState {
  const state = useContext(Ctx);
  if (!state) throw new Error("usePlannerState 要在 PlannerStateProvider 里面用");
  return state;
}

export const VALIDATION_TEXT: Record<ValidationStatus, string> = {
  passed: "通过",
  warning: "有警告",
  failed: "未通过",
};

/**
 * 右上角的标注：当前选中的模型，和当前这份行程的校验结果。
 * 行程是另一个模型排的时候写明是谁排的，免得把"选中的模型"和"这份行程的结果"混在一起。没有就不显示。
 */
export function PlannerCorner() {
  const { providerLabel, validation, validationBy } = usePlannerState();
  if (!providerLabel && !validation) return null;
  const parts: string[] = [];
  if (providerLabel) parts.push(`模型 ${providerLabel}`);
  if (validation) {
    const other = validationBy && validationBy !== providerLabel ? `${validationBy}排的行程 ` : "";
    parts.push(`${other}校验 ${VALIDATION_TEXT[validation]}`);
  }
  return <Label>{parts.join(" · ")}</Label>;
}
