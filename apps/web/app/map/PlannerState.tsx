"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
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
  setValidation: (status: ValidationStatus | null) => void;
}

const Ctx = createContext<PlannerState | null>(null);

export function PlannerStateProvider({ children }: { children: ReactNode }) {
  const [provider, setProviderId] = useState<LlmProviderId | null>(null);
  const [providerLabel, setProviderLabel] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationStatus | null>(null);
  const value = useMemo<PlannerState>(
    () => ({
      provider,
      providerLabel,
      setProvider: (id, label) => {
        setProviderId(id);
        setProviderLabel(label);
      },
      validation,
      setValidation,
    }),
    [provider, providerLabel, validation],
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

/** 右上角的标注：当前模型和当前行程的校验结果。没有就不显示 */
export function PlannerCorner() {
  const { providerLabel, validation } = usePlannerState();
  if (!providerLabel && !validation) return null;
  return (
    <Label>
      {providerLabel ? `模型 ${providerLabel}` : ""}
      {providerLabel && validation ? " · " : ""}
      {validation ? `校验 ${VALIDATION_TEXT[validation]}` : ""}
    </Label>
  );
}
