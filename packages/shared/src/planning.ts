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
}

export interface Conversation {
  conversationId: string;
  preferences: TravelerPreferences;
  itineraryId: string | null;
  messages: ConversationMessage[];
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
  error: LlmError | null;
}
