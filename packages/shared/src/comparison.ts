/**
 * 双模型并排对比（板块 6）。和后端 apps/api/app/schemas/comparison.py 一致。
 * 所有数字都由后端程序算好，前端只显示，不算数，也不写"哪个模型更好"。
 */
import type { ComparisonRow, Emphasis, ItineraryVersion, PlanMetrics, PlanningStage, TravelerPreferences, ValidationStatus } from "./planning";
import type { LlmError } from "./llm";

export interface CallStats {
  /** 网关调用次数（排行程 1 次、修正 0 或 1 次；抽偏好两边共用，不算在任何一边） */
  callCount: number;
  /** 实际发出的请求次数，含重试和让模型重答 */
  requestCount: number;
  failedCalls: number;
  retriedCalls: number;
  reaskedCalls: number;
  modelMs: number;
  inputTokens: number | null;
  outputTokens: number | null;
  tokensUnknownCalls: number;
  byTask: Record<string, number>;
}

/** "通过"指没有错误（资料还没核实，警告几乎免不了） */
export interface QualityMetrics {
  firstPassed: boolean;
  firstStatus: ValidationStatus;
  firstErrorCount: number;
  firstWarningCount: number;
  firstErrorCodes: Record<string, number>;
  repaired: boolean;
  finalPassed: boolean;
  finalStatus: ValidationStatus;
  finalErrorCount: number;
  finalWarningCount: number;
  finalErrorCodes: Record<string, number>;
  /** 第一版里 id 在整个景点库里都找不到的 */
  firstFabricatedPoiIds: string[];
  /** 第一版里在库里、但这次不能用的（用户不去、暂停开放、侧重没给） */
  firstOffListPoiIds: string[];
  finalFabricatedPoiIds: string[];
  finalOffListPoiIds: string[];
}

export interface SideResult {
  provider: string;
  providerLabel: string;
  model: string | null;
  versionId: string | null;
  /** 模型没排出来时的说明；这时 quality 和 plan 为 null */
  error: string | null;
  quality: QualityMetrics | null;
  plan: PlanMetrics | null;
  calls: CallStats;
  wallMs: number;
}

export interface PoiRef {
  poiId: string;
  name: string;
}

export interface DayDiff {
  dayNumber: number;
  /** 两边这一天的景点，第一个是左边 */
  orders: PoiRef[][];
  common: PoiRef[];
  /** 都有的不到 2 个时为 null */
  sameOrder: boolean | null;
}

export interface MovedPoi {
  poiId: string;
  name: string;
  days: number[];
}

export interface PlanDiff {
  onlyLeft: PoiRef[];
  onlyRight: PoiRef[];
  both: PoiRef[];
  days: DayDiff[];
  moved: MovedPoi[];
  nearDuplicate: string | null;
}

export interface ComparisonTable {
  labels: string[];
  rows: ComparisonRow[];
}

/** GET /api/comparisons/{id} */
export interface ModelComparison {
  id: string;
  createdAt: string;
  request: string;
  preferences: TravelerPreferences;
  preferencesSource: "extracted" | "given";
  extractor: string | null;
  extractorCalls: CallStats | null;
  emphasis: Emphasis;
  emphasisLabel: string;
  defaultsUsed: string[];
  sides: SideResult[];
  diff: PlanDiff | null;
  table: ComparisonTable;
  evalRequestId: string | null;
  /** 两边的行程版本，顺序和 sides 一样；没排出来的一边为 null */
  versions: (ItineraryVersion | null)[];
}

export interface SideBrief {
  providerLabel: string;
  model: string | null;
  error: boolean;
  firstPassed: boolean | null;
  finalPassed: boolean | null;
}

/** GET /api/comparisons 的一条 */
export interface ModelComparisonSummary {
  id: string;
  createdAt: string;
  request: string;
  emphasisLabel: string;
  evalRequestId: string | null;
  sides: SideBrief[];
}

export interface CompareSideProgress {
  provider: string;
  label: string;
  stages: PlanningStage[];
}

/** GET /api/comparison-jobs/{id} */
export interface CompareJob {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed";
  request: string;
  emphasis: string;
  stages: PlanningStage[];
  sides: CompareSideProgress[];
  comparisonId: string | null;
  error: LlmError | null;
}
