/**
 * 对话、规划和行程的数据结构，和后端对应：
 * apps/api/app/schemas/planning.py、itinerary.py、api.py。
 * 字段说明见 docs/architecture/api-contracts.md 的"对话和规划"一节和 docs/architecture/ai-planning-pipeline.md。
 */
import type { LlmError } from "./llm";
import type { Coordinates, OpeningHours, Payment, PoiFact, Reservation, Ticket } from "./poi";
import type { Route } from "./route";

export type Pace = "relaxed" | "moderate" | "intensive";

/** 模型从对话里抽出来的偏好。没说的是 null 或空列表 */
export interface TravelerPreferences {
  days: number | null;
  startDate: string | null;
  dateUndecided: boolean;
  pace: Pace | null;
  interests: string[];
  budget: "low" | "medium" | "high" | null;
  party: "solo" | "couple" | "friends" | "family" | "elderly" | null;
  transport: "metro" | "walk" | "taxi" | null;
  mustVisit: string[];
  avoid: string[];
  notes: string | null;
}

export interface TripFrame {
  days: number;
  /** 日期未定时为 null */
  startDate: string | null;
  pace: Pace;
}

export type ValidationStatus = "passed" | "warning" | "failed";

export interface ValidationIssue {
  level: "error" | "warning";
  /** 机器读的类型，例如 closed-day、hours-unknown */
  code: string;
  /** 给人读的说明，写明是哪个景点、哪一项、为什么 */
  message: string;
  dayNumber: number | null;
  poiId: string | null;
  /** 依据的是景点的哪几项资料，例如 ["openingHours"] */
  fields: string[];
}

export interface ValidationReport {
  status: ValidationStatus;
  issues: ValidationIssue[];
}

/** 行程卡上用到的景点资料，程序从景点库取的，带核实状态 */
export interface StopFacts {
  openingHours: PoiFact<OpeningHours>;
  reservation: PoiFact<Reservation>;
  ticket: PoiFact<Ticket>;
  payment: PoiFact<Payment>;
  recommendedDurationMinutes: PoiFact<number>;
}

export interface ItineraryStop {
  poiId: string;
  name: string;
  district: string;
  category: string;
  location: Coordinates;
  arrive: string;
  leave: string;
  /** 模型写的"为什么这样排" */
  reason: string;
  facts: StopFacts;
}

/** 相邻两站之间的交通。时间是程序向高德查的 */
export interface ItineraryLeg {
  fromPoiId: string;
  toPoiId: string;
  route: Route;
  /** 为什么选这种方式 */
  choice: string;
}

export interface ItineraryDay {
  dayNumber: number;
  date: string | null;
  theme: string;
  stops: ItineraryStop[];
  legs: ItineraryLeg[];
}

export interface PlannerInfo {
  provider: string;
  providerLabel: string;
  /** 对方返回的真实模型名 */
  model: string | null;
  /** 1：没修正；2：把错误交给模型修正过一次 */
  rounds: number;
  firstRoundStatus: ValidationStatus;
  firstRoundErrors: number;
}

export interface ItineraryVersion {
  id: string;
  itineraryId: string;
  versionNumber: number;
  createdAt: string;
  title: string;
  city: string;
  frame: TripFrame;
  preferences: TravelerPreferences;
  /** 程序替用户补上的默认值，界面上要写出来 */
  defaultsUsed: string[];
  days: ItineraryDay[];
  validation: ValidationReport;
  planner: PlannerInfo;
  /** 资料状态按哪一天算的 */
  dataAsOf: string;
  /** 板块 5B：这份方案的侧重；之前存的版本为 null */
  emphasis?: Emphasis | null;
  /** 程序算的数字，比较方案用；之前存的版本为 null */
  metrics?: PlanMetrics | null;
  /** 板块 6：第一版的完整校验报告；之前存的版本为 null */
  firstValidation?: ValidationReport | null;
}

/** 三种侧重：经典必去、轻松少走路、深度文化 */
export type Emphasis = "classic" | "relaxed" | "culture";

export interface StopTicket {
  dayNumber: number;
  poiId: string;
  name: string;
  /** 都为 null 表示资料里没有票价 */
  minCny: number | null;
  maxCny: number | null;
  label: string;
}

export interface DayMetrics {
  dayNumber: number;
  stopCount: number;
  end: string | null;
  transportMinutes: number;
  walkingMeters: number;
  walkingUnknownLegs: number;
}

/** 一份方案的数字，程序从行程快照算的 */
export interface PlanMetrics {
  poiIds: string[];
  poiNames: string[];
  stopCount: number;
  transportMinutes: number;
  minutesByMode: Record<string, number>;
  unknownLegs: number;
  walkingMeters: number;
  walkingUnknownLegs: number;
  tickets: StopTicket[];
  ticketMinCny: number;
  ticketMaxCny: number;
  ticketComplete: boolean;
  validationStatus: ValidationStatus;
  errorCount: number;
  warningCount: number;
  rounds: number;
  days: DayMetrics[];
}

/** 对比表的一行：每份方案一格，texts 是程序写好的显示文字 */
export interface ComparisonRow {
  key: string;
  label: string;
  texts: string[];
  values: (number | null)[];
  note: string | null;
}

export interface PlanComparison {
  labels: string[];
  rows: ComparisonRow[];
}

/** 一轮里的一份方案 */
export interface RoundPlan {
  emphasis: Emphasis;
  label: string;
  itineraryId: string | null;
  versionId: string | null;
  shown: boolean;
  /** 不展示的原因 */
  removedReason: string | null;
}

/** 一次规划产生的一轮方案（GET /api/planning-rounds/{id}） */
export interface PlanningRound {
  id: string;
  createdAt: string;
  conversationId: string;
  roundNumber: number;
  provider: string;
  providerLabel: string;
  plans: RoundPlan[];
  defaultsUsed: string[];
  /** 展示的几份方案的版本，顺序和 plans 里 shown 的一致 */
  versions: ItineraryVersion[];
  /** 展示的几份之间的比较表；一份都没展示时为 null */
  comparison: PlanComparison | null;
}

export type ReplyKind = "question" | "itinerary" | "failed" | "error";

export interface ConversationMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  kind: ReplyKind | null;
  provider: string | null;
  itineraryVersionId: string | null;
  /** 板块 5B：这条回复带出的那一轮方案 */
  planningRoundId?: string | null;
}

export interface Conversation {
  conversationId: string;
  preferences: TravelerPreferences;
  itineraryId: string | null;
  messages: ConversationMessage[];
  /** 还在规划中的任务；刷新页面后接着显示进度 */
  runningJobId: string | null;
}

export interface SendMessageResponse {
  messageId: number;
  planningJobId: string;
  status: PlanningJob["status"];
}

export interface PlanningStage {
  id: string;
  label: string;
}

export interface PlanningJob {
  jobId: string;
  conversationId: string;
  /** failed 只表示任务本身出错（模型调用失败等）；行程没通过校验时是 completed，kind 是 failed */
  status: "queued" | "running" | "completed" | "failed";
  stage: string | null;
  stages: PlanningStage[];
  kind: "question" | "itinerary" | "failed" | null;
  reply: string | null;
  provider: string | null;
  itineraryVersionId: string | null;
  planningRoundId?: string | null;
  error: LlmError | null;
}
